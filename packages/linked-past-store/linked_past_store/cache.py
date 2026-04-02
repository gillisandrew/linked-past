"""Content-addressable local cache for OCI artifacts.

Stores pulled artifacts by manifest digest so repeated pulls of the same
content are instant. Similar to Docker's layer cache.

Cache layout:
  {cache_dir}/
  ├── manifests/           # {registry}/{dataset}/{tag} → digest mapping
  │   └── ghcr.io/
  │       └── gillisandrew/
  │           └── linked-past/
  │               └── dprr/
  │                   └── latest    # contains: sha256:2aee...
  ├── blobs/               # Content-addressable storage
  │   └── sha256/
  │       └── 2aee.../     # Extracted artifact files
  │           ├── dprr.ttl
  │           └── void.ttl
  └── gc.json              # Last access times for garbage collection
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import oras.client


@dataclass
class LayerInfo:
    """Metadata for a single OCI layer."""

    digest: str       # "sha256:abc123..."
    filename: str     # "dprr.ttl" or "_schema.yaml"
    size: int         # bytes
    is_sidecar: bool  # True if filename starts with "_"

logger = logging.getLogger(__name__)


def _default_cache_dir() -> Path:
    """Default cache directory following XDG."""
    import os

    explicit = os.environ.get("LINKED_PAST_CACHE_DIR")
    if explicit:
        return Path(explicit)
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "linked-past"


def _ref_to_path(ref: str) -> str:
    """Convert an OCI ref to a filesystem-safe path segment."""
    # ghcr.io/gillisandrew/linked-past/dprr:latest → ghcr.io/gillisandrew/linked-past/dprr/latest
    return ref.replace(":", "/")


def _fetch_manifest_json(ref: str) -> str | None:
    """Fetch manifest JSON from OCI registry using the Python oras library."""
    try:
        import oras.client

        client = oras.client.OrasClient()
        manifest = client.get_manifest(ref)
        if isinstance(manifest, dict):
            return json.dumps(manifest)
        return None
    except Exception as e:
        logger.debug("Failed to fetch manifest for %s: %s", ref, e)
        return None


def _resolve_digest(ref: str) -> str | None:
    """Resolve an OCI ref to its manifest digest without downloading.

    Computes SHA-256 of the canonical manifest JSON.
    """
    import hashlib

    raw = _fetch_manifest_json(ref)
    if not raw:
        return None
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"sha256:{digest}"


def _verify_digest(path: Path, expected: str) -> bool:
    """Verify a file's SHA-256 digest matches the expected OCI digest."""
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}" == expected


class ArtifactCache:
    """Content-addressable local cache for OCI artifacts."""

    def __init__(self, cache_dir: Path | None = None):
        self._cache_dir = cache_dir or _default_cache_dir()
        self._manifests_dir = self._cache_dir / "manifests"
        self._blobs_dir = self._cache_dir / "blobs" / "sha256"
        self._layers_dir = self._cache_dir / "layers"
        self._gc_path = self._cache_dir / "gc.json"

    def get(self, ref: str) -> Path | None:
        """Check if an artifact is cached. Returns blob directory or None."""
        # Check tag → digest mapping
        manifest_path = self._manifests_dir / _ref_to_path(ref)
        if not manifest_path.exists():
            return None

        digest = manifest_path.read_text().strip()
        blob_dir = self._blobs_dir / digest.replace("sha256:", "")
        if not blob_dir.exists() or not any(blob_dir.iterdir()):
            return None

        # Update access time for GC
        self._touch(digest)
        logger.info("Cache hit: %s → %s", ref, digest[:20])
        return blob_dir

    def put(self, ref: str, digest: str, blob_dir: Path) -> None:
        """Record a cached artifact."""
        # Store tag → digest mapping
        manifest_path = self._manifests_dir / _ref_to_path(ref)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(digest)

        self._touch(digest)
        logger.info("Cached: %s → %s (%d files)", ref, digest[:20], len(list(blob_dir.iterdir())))

    def pull(self, ref: str, force: bool = False) -> Path:
        """Pull an artifact, using per-layer cache when possible.

        Args:
            ref: OCI reference (e.g., "ghcr.io/myorg/dataset:v1.0")
            force: If True, bypass cache and re-download all layers

        Returns:
            Path to the blob directory containing artifact files
        """
        import tempfile

        # Quick check: existing cache hit by tag (unchanged manifest)
        if not force:
            cached = self.get(ref)
            if cached:
                return cached

        # Resolve manifest digest
        digest = _resolve_digest(ref)

        # Check if we have this exact manifest assembled already
        if digest and not force:
            blob_dir = self._blobs_dir / digest.replace("sha256:", "")
            if blob_dir.exists() and any(blob_dir.iterdir()):
                self.put(ref, digest, blob_dir)
                logger.info("Cache hit by digest: %s → %s", ref, digest[:20])
                return blob_dir

        # Try layer-aware pull via manifest
        manifest = self.fetch_manifest(ref)
        if manifest and manifest.get("layers"):
            layers = self.parse_layers(manifest)

            # Download missing layers in parallel with progress
            tmp_dir = self._cache_dir / "tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)

            def _fmt_size(n: int) -> str:
                if n >= 1_000_000:
                    return f"{n / 1_000_000:.1f} MB"
                if n >= 1_000:
                    return f"{n / 1_000:.1f} KB"
                return f"{n} B"

            # Partition into cached vs needs-download
            to_download = []
            for layer in layers:
                if self.has_layer(layer.digest):
                    print(f"  {layer.filename:20s} Cached ({layer.digest[:12]})", flush=True)
                else:
                    to_download.append(layer)

            if to_download:
                import threading
                from concurrent.futures import ThreadPoolExecutor, as_completed

                lock = threading.Lock()
                completed_count = 0
                total = len(to_download)
                total_bytes = sum(layer.size for layer in to_download)

                print(f"  Downloading {total} layer(s) ({_fmt_size(total_bytes)})...", flush=True)

                def _fetch_layer(layer: LayerInfo) -> str:
                    nonlocal completed_count
                    with tempfile.NamedTemporaryFile(
                        dir=tmp_dir, suffix=f"_{layer.filename}", delete=False
                    ) as tmp_file:
                        tmp_path = Path(tmp_file.name)
                    try:
                        self._download_layer(ref, layer.digest, str(tmp_path))
                        self.put_layer(layer.digest, layer.filename, tmp_path)
                    finally:
                        tmp_path.unlink(missing_ok=True)
                    with lock:
                        completed_count += 1
                        print(
                            f"  {layer.filename:20s} Done ({_fmt_size(layer.size)}) [{completed_count}/{total}]",
                            flush=True,
                        )
                    return layer.filename

                with ThreadPoolExecutor(max_workers=4) as pool:
                    futures = {pool.submit(_fetch_layer, layer): layer for layer in to_download}
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            layer = futures[future]
                            logger.warning("Failed to download %s: %s", layer.filename, e)

            # Resolve manifest digest if we didn't have it
            if not digest:
                digest = _resolve_digest(ref) or f"sha256:unknown-{ref}"

            # Assemble blob directory from layers
            blob_dir = self.assemble_blob_dir(digest, layers)
            self.put(ref, digest, blob_dir)
            return blob_dir

        # Fallback: manifest fetch failed — use legacy full pull
        logger.info("Manifest unavailable, falling back to full pull for %s", ref)
        if not digest:
            import hashlib

            digest = f"sha256:{hashlib.sha256(ref.encode()).hexdigest()}"

        blob_dir = self._blobs_dir / digest.replace("sha256:", "")
        blob_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Downloading %s ...", ref)

        client = oras.client.OrasClient()
        files = client.pull(target=ref, outdir=str(blob_dir))

        if not files:
            raise RuntimeError(f"No files pulled from {ref}")

        # Populate layer cache from downloaded files for future use
        if manifest:
            for layer in self.parse_layers(manifest):
                src = blob_dir / layer.filename
                if src.exists():
                    self.put_layer(layer.digest, layer.filename, src)

        if not digest.startswith("sha256:unknown"):
            self.put(ref, digest, blob_dir)
        else:
            resolved = _resolve_digest(ref) or digest
            self.put(ref, resolved, blob_dir)

        return blob_dir

    def find_ttl(self, blob_dir: Path) -> list[Path]:
        """Find all .ttl files in a blob directory."""
        return sorted(blob_dir.glob("*.ttl"))

    def parse_layers(self, manifest: dict) -> list[LayerInfo]:
        """Parse OCI manifest layers into LayerInfo objects."""
        layers = []
        for layer in manifest.get("layers", []):
            annotations = layer.get("annotations", {})
            filename = annotations.get("org.opencontainers.image.title", "unknown")
            layers.append(LayerInfo(
                digest=layer["digest"],
                filename=filename,
                size=layer.get("size", 0),
                is_sidecar=filename.startswith("_"),
            ))
        return layers

    def fetch_manifest(self, ref: str) -> dict | None:
        """Fetch manifest from registry and cache it locally."""
        raw = _fetch_manifest_json(ref)
        if not raw:
            return None
        manifest = json.loads(raw)
        # Cache the manifest JSON alongside the digest file
        manifest_path = self._manifests_dir / (_ref_to_path(ref) + ".json")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(raw)
        return manifest

    def get_manifest(self, ref: str) -> dict | None:
        """Get cached manifest for a ref, or None."""
        manifest_path = self._manifests_dir / (_ref_to_path(ref) + ".json")
        if manifest_path.exists():
            return json.loads(manifest_path.read_text())
        return None

    # -- Per-layer cache storage --

    def has_layer(self, digest: str) -> bool:
        """Check if a layer blob exists in the layer cache."""
        layer_dir = self._layers_dir / digest.replace("sha256:", "")
        return layer_dir.exists() and any(layer_dir.iterdir())

    def put_layer(self, digest: str, filename: str, src_path: Path) -> None:
        """Store a file in the per-layer cache."""
        import shutil

        layer_dir = self._layers_dir / digest.replace("sha256:", "")
        layer_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, layer_dir / filename)
        self._touch_layer(digest)

    def get_layer_path(self, digest: str, filename: str) -> Path | None:
        """Get the path to a cached layer file, or None."""
        layer_path = self._layers_dir / digest.replace("sha256:", "") / filename
        if layer_path.exists():
            return layer_path
        return None

    def assemble_blob_dir(self, manifest_digest: str, layers: list[LayerInfo]) -> Path:
        """Assemble a blob directory from cached layers using symlinks (copy fallback)."""
        import shutil

        blob_dir = self._blobs_dir / manifest_digest.replace("sha256:", "")
        blob_dir.mkdir(parents=True, exist_ok=True)

        for layer in layers:
            src = self.get_layer_path(layer.digest, layer.filename)
            if src is None:
                raise FileNotFoundError(
                    f"Layer {layer.digest} ({layer.filename}) not in cache"
                )
            dst = blob_dir / layer.filename
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            try:
                dst.symlink_to(src.resolve())
            except OSError:
                # Symlinks not supported (some Windows configs) — fall back to copy
                shutil.copy2(src, dst)

        # Record layer references for GC
        gc_data = self._load_gc()
        gc_data.setdefault("manifest_layers", {})[manifest_digest] = [
            layer.digest for layer in layers
        ]
        self._save_gc(gc_data)

        return blob_dir

    def _download_layer(self, ref: str, digest: str, outpath: str) -> None:
        """Download a single layer blob by digest and verify its content hash."""
        repo = ref.rsplit(":", 1)[0]
        try:
            client = oras.client.OrasClient()
            response = client.get_blob(repo, digest)
            with open(outpath, "wb") as f:
                f.write(response.content)
        except Exception as e:
            logger.warning("Blob fetch failed for %s: %s", digest[:20], e)
            raise

        # Verify downloaded content matches declared digest
        if not _verify_digest(Path(outpath), digest):
            Path(outpath).unlink(missing_ok=True)
            raise RuntimeError(
                f"Digest verification failed for {digest}: "
                f"downloaded content does not match expected hash"
            )

    def digest_for(self, ref: str) -> str | None:
        """Get the cached digest for a ref, or None."""
        manifest_path = self._manifests_dir / _ref_to_path(ref)
        if manifest_path.exists():
            return manifest_path.read_text().strip()
        return None

    def list_cached(self) -> list[dict]:
        """List all cached artifacts."""
        entries = []
        gc = self._load_gc()
        for digest_dir in sorted(self._blobs_dir.iterdir()) if self._blobs_dir.exists() else []:
            digest = f"sha256:{digest_dir.name}"
            files = list(digest_dir.iterdir())
            size = sum(f.stat().st_size for f in files if f.is_file())
            entries.append({
                "digest": digest,
                "files": len(files),
                "size_bytes": size,
                "last_accessed": gc.get(digest, "unknown"),
            })
        return entries

    def gc(self, max_age_days: int = 30) -> int:
        """Remove cached blobs and orphaned layers not accessed in max_age_days.

        Returns count of items removed (blobs + layers combined).
        """
        import shutil

        gc_data = self._load_gc()
        now = datetime.now(timezone.utc)
        removed = 0

        # Phase 1: GC manifest blobs (existing behavior), track surviving manifests
        surviving_manifests: set[str] = set()
        for digest_dir in list(self._blobs_dir.iterdir()) if self._blobs_dir.exists() else []:
            digest = f"sha256:{digest_dir.name}"
            last_access = gc_data.get(digest)
            if last_access:
                try:
                    last_dt = datetime.fromisoformat(last_access)
                    if (now - last_dt).days <= max_age_days:
                        surviving_manifests.add(digest)
                        continue
                except ValueError:
                    pass

            shutil.rmtree(digest_dir, ignore_errors=True)
            gc_data.pop(digest, None)
            gc_data.get("manifest_layers", {}).pop(digest, None)
            removed += 1
            logger.info("GC: removed manifest blob %s", digest[:20])

        # Phase 2: Collect layer digests referenced by surviving manifests
        referenced_layers: set[str] = set()
        for manifest_digest in surviving_manifests:
            layer_digests = gc_data.get("manifest_layers", {}).get(manifest_digest, [])
            referenced_layers.update(layer_digests)

        # Remove orphaned layers not referenced AND not recently accessed
        layer_access = gc_data.get("layers", {})
        for layer_dir in list(self._layers_dir.iterdir()) if self._layers_dir.exists() else []:
            layer_digest = f"sha256:{layer_dir.name}"
            if layer_digest in referenced_layers:
                continue  # Referenced by a surviving manifest — keep
            last_access = layer_access.get(layer_digest)
            if last_access:
                try:
                    last_dt = datetime.fromisoformat(last_access)
                    if (now - last_dt).days <= max_age_days:
                        continue  # Recently accessed — keep
                except ValueError:
                    pass

            shutil.rmtree(layer_dir, ignore_errors=True)
            layer_access.pop(layer_digest, None)
            removed += 1
            logger.info("GC: removed orphaned layer %s", layer_digest[:20])

        self._save_gc(gc_data)
        return removed

    def _touch(self, digest: str) -> None:
        gc = self._load_gc()
        gc[digest] = datetime.now(timezone.utc).isoformat()
        self._save_gc(gc)

    def _touch_layer(self, digest: str) -> None:
        gc = self._load_gc()
        gc.setdefault("layers", {})[digest] = datetime.now(timezone.utc).isoformat()
        self._save_gc(gc)

    def _load_gc(self) -> dict:
        if self._gc_path.exists():
            return json.loads(self._gc_path.read_text())
        return {}

    def _save_gc(self, data: dict) -> None:
        self._gc_path.parent.mkdir(parents=True, exist_ok=True)
        self._gc_path.write_text(json.dumps(data, indent=2))
