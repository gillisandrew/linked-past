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
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import oras.client

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


def _resolve_digest(ref: str) -> str | None:
    """Resolve an OCI ref to its manifest digest without downloading."""
    try:
        result = subprocess.run(
            ["oras", "manifest", "fetch", ref, "--descriptor"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        descriptor = json.loads(result.stdout)
        return descriptor.get("digest")
    except Exception as e:
        logger.debug("Failed to resolve digest for %s: %s", ref, e)
        return None


class ArtifactCache:
    """Content-addressable local cache for OCI artifacts."""

    def __init__(self, cache_dir: Path | None = None):
        self._cache_dir = cache_dir or _default_cache_dir()
        self._manifests_dir = self._cache_dir / "manifests"
        self._blobs_dir = self._cache_dir / "blobs" / "sha256"
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
        """Pull an artifact, using cache if available.

        Args:
            ref: OCI reference (e.g., "ghcr.io/myorg/dataset:v1.0")
            force: If True, bypass cache and re-download

        Returns:
            Path to the blob directory containing artifact files
        """
        if not force:
            cached = self.get(ref)
            if cached:
                return cached

        # Resolve the digest first (cheap HEAD request)
        digest = _resolve_digest(ref)

        # Check if we have this digest even if the tag mapping is stale
        if digest and not force:
            blob_dir = self._blobs_dir / digest.replace("sha256:", "")
            if blob_dir.exists() and any(blob_dir.iterdir()):
                # Update tag mapping and return
                self.put(ref, digest, blob_dir)
                logger.info("Cache hit by digest: %s → %s", ref, digest[:20])
                return blob_dir

        # Cache miss — download
        if digest:
            blob_dir = self._blobs_dir / digest.replace("sha256:", "")
        else:
            # No digest available (offline?) — use ref hash as fallback
            import hashlib

            ref_hash = hashlib.sha256(ref.encode()).hexdigest()
            blob_dir = self._blobs_dir / ref_hash

        blob_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Downloading %s ...", ref)

        client = oras.client.OrasClient()
        files = client.pull(target=ref, outdir=str(blob_dir))

        if not files:
            raise RuntimeError(f"No files pulled from {ref}")

        # If we didn't have a digest before, try to get it now
        if not digest:
            digest = _resolve_digest(ref) or f"sha256:unknown-{ref}"

        self.put(ref, digest, blob_dir)
        return blob_dir

    def find_ttl(self, blob_dir: Path) -> list[Path]:
        """Find all .ttl files in a blob directory."""
        return sorted(blob_dir.glob("*.ttl"))

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
        """Remove cached blobs not accessed in max_age_days. Returns count removed."""
        gc_data = self._load_gc()
        now = datetime.now(timezone.utc)
        removed = 0

        for digest_dir in list(self._blobs_dir.iterdir()) if self._blobs_dir.exists() else []:
            digest = f"sha256:{digest_dir.name}"
            last_access = gc_data.get(digest)
            if last_access:
                try:
                    last_dt = datetime.fromisoformat(last_access)
                    if (now - last_dt).days <= max_age_days:
                        continue
                except ValueError:
                    pass

            import shutil

            shutil.rmtree(digest_dir, ignore_errors=True)
            gc_data.pop(digest, None)
            removed += 1
            logger.info("GC: removed %s", digest[:20])

        self._save_gc(gc_data)
        return removed

    def _touch(self, digest: str) -> None:
        gc = self._load_gc()
        gc[digest] = datetime.now(timezone.utc).isoformat()
        self._save_gc(gc)

    def _load_gc(self) -> dict:
        if self._gc_path.exists():
            return json.loads(self._gc_path.read_text())
        return {}

    def _save_gc(self, data: dict) -> None:
        self._gc_path.parent.mkdir(parents=True, exist_ok=True)
        self._gc_path.write_text(json.dumps(data, indent=2))
