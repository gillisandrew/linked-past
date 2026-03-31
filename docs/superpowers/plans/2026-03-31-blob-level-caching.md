# Blob-Level Local Readthrough Caching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-OCI-layer blob caching in ArtifactCache so dataset updates only re-download changed files, plus smart store invalidation that skips Oxigraph rebuilds when only sidecar files change.

**Architecture:** Parse OCI manifest JSON to get per-layer digests and filenames. Cache each layer by its content digest in a `layers/` directory. On pull, assemble the blob directory via symlinks (with copy fallback). Compare data-file digests between old and new manifests to decide whether to invalidate the Oxigraph store or just copy new sidecars.

**Tech Stack:** Python stdlib (json, pathlib, shutil, os), oras CLI (`manifest fetch`, `blob fetch`), existing ArtifactCache infrastructure.

---

## File Structure

```
packages/linked-past-store/linked_past_store/
  cache.py          ← MODIFY: add LayerInfo, _layers_dir, manifest parsing, layer-aware pull, layer GC
  pull.py           ← MODIFY: smart store invalidation in pull_for_dataset
  cli.py            ← MODIFY: cache clear wipes layers/

packages/linked-past-store/tests/
  test_cache.py     ← CREATE: tests for manifest parsing, layer cache, GC
  test_pull.py      ← MODIFY: add smart invalidation tests
```

---

### Task 0: Fix pull_dataset to copy all files (not just *.ttl)

**Files:**
- Modify: `packages/linked-past-store/linked_past_store/pull.py`
- Modify: `packages/linked-past-store/tests/test_pull.py`

The current `pull_dataset` only copies `*.ttl` files from the blob directory to the output directory. This means `_schema.yaml` never reaches the dataset directory, breaking the sidecar update path. Fix: copy ALL files from the blob dir.

- [ ] **Step 1: Write failing test**

Add to `test_pull.py`:

```python
def test_pull_dataset_copies_all_files(tmp_path):
    """pull_dataset should copy all files, not just .ttl."""
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "output"

    def fake_pull(target, outdir):
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "data.ttl").write_text("rdf content")
        (outdir / "_schema.yaml").write_text("classes: {}")
        (outdir / "_void.ttl").write_text("void content")
        return [str(outdir / "data.ttl")]

    with (
        patch("linked_past_store.cache.oras.client.OrasClient") as MockClient,
        patch("linked_past_store.cache._default_cache_dir", return_value=cache_dir),
        patch("linked_past_store.cache._resolve_digest", return_value="sha256:abc123"),
    ):
        mock = MagicMock()
        MockClient.return_value = mock
        mock.pull.side_effect = fake_pull
        result = pull_dataset("ghcr.io/test/dataset:v1", output_dir, force=True)

    assert (output_dir / "data.ttl").exists()
    assert (output_dir / "_schema.yaml").exists()
    assert (output_dir / "_void.ttl").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/linked-past-store/tests/test_pull.py::test_pull_dataset_copies_all_files -v`
Expected: FAIL — `_schema.yaml` not copied.

- [ ] **Step 3: Fix pull_dataset to copy all files**

In `pull.py`, replace the `find_ttl` + copy loop with a copy of all files:

```python
def pull_dataset(ref, output_dir, force=False):
    # ... (cache.pull unchanged) ...

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cache = ArtifactCache()
    blob_dir = cache.pull(ref, force=force)

    # Copy ALL files from cache to output directory
    all_files = [f for f in blob_dir.iterdir() if f.is_file() or f.is_symlink()]
    if not all_files:
        raise RuntimeError(f"No files found in artifact {ref}")

    ttl_files = []
    for src in all_files:
        dst = output_dir / src.name
        if dst != src:
            shutil.copy2(src, dst, follow_symlinks=True)
        if src.suffix == ".ttl":
            ttl_files.append(dst)

    if not ttl_files:
        raise RuntimeError(f"No .ttl file found in artifact {ref}")

    logger.info("Pulled %s → %s (%d files)", ref, output_dir, len(all_files))
    return ttl_files[0]
```

Also add `import shutil` at the top of `pull.py` if not already present.

- [ ] **Step 4: Run all pull tests**

Run: `uv run pytest packages/linked-past-store/tests/test_pull.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-store/linked_past_store/pull.py packages/linked-past-store/tests/test_pull.py
git commit -m "fix: pull_dataset copies all files from blob dir, not just *.ttl"
```

---

### Task 1: LayerInfo dataclass and manifest parsing

**Files:**
- Modify: `packages/linked-past-store/linked_past_store/cache.py`
- Create: `packages/linked-past-store/tests/test_cache.py`

- [ ] **Step 1: Write failing tests for manifest parsing**

```python
"""Tests for ArtifactCache layer-level caching."""

import json

from linked_past_store.cache import LayerInfo, ArtifactCache


SAMPLE_MANIFEST = {
    "schemaVersion": 2,
    "mediaType": "application/vnd.oci.image.manifest.v1+json",
    "config": {"digest": "sha256:config000", "size": 0},
    "layers": [
        {
            "mediaType": "application/x-turtle",
            "digest": "sha256:aaa111",
            "size": 45000000,
            "annotations": {"org.opencontainers.image.title": "dprr.ttl"},
        },
        {
            "mediaType": "application/x-turtle",
            "digest": "sha256:bbb222",
            "size": 1200,
            "annotations": {"org.opencontainers.image.title": "_void.ttl"},
        },
        {
            "mediaType": "application/octet-stream",
            "digest": "sha256:ccc333",
            "size": 800,
            "annotations": {"org.opencontainers.image.title": "_schema.yaml"},
        },
    ],
}


class TestLayerInfo:
    def test_data_file_not_sidecar(self):
        layer = LayerInfo(digest="sha256:aaa", filename="dprr.ttl", size=100, is_sidecar=False)
        assert not layer.is_sidecar

    def test_sidecar_file(self):
        layer = LayerInfo(digest="sha256:bbb", filename="_void.ttl", size=50, is_sidecar=True)
        assert layer.is_sidecar


class TestParseManifestLayers:
    def test_parses_all_layers(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        layers = cache.parse_layers(SAMPLE_MANIFEST)
        assert len(layers) == 3

    def test_extracts_filenames(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        layers = cache.parse_layers(SAMPLE_MANIFEST)
        filenames = [l.filename for l in layers]
        assert "dprr.ttl" in filenames
        assert "_void.ttl" in filenames
        assert "_schema.yaml" in filenames

    def test_classifies_sidecars(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        layers = cache.parse_layers(SAMPLE_MANIFEST)
        by_name = {l.filename: l for l in layers}
        assert not by_name["dprr.ttl"].is_sidecar
        assert by_name["_void.ttl"].is_sidecar
        assert by_name["_schema.yaml"].is_sidecar

    def test_extracts_digests_and_sizes(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        layers = cache.parse_layers(SAMPLE_MANIFEST)
        by_name = {l.filename: l for l in layers}
        assert by_name["dprr.ttl"].digest == "sha256:aaa111"
        assert by_name["dprr.ttl"].size == 45000000
        assert by_name["_void.ttl"].digest == "sha256:bbb222"

    def test_handles_missing_title_annotation(self, tmp_path):
        manifest = {
            "layers": [{
                "digest": "sha256:xxx",
                "size": 10,
                "annotations": {},
            }],
        }
        cache = ArtifactCache(tmp_path / "cache")
        layers = cache.parse_layers(manifest)
        assert len(layers) == 1
        assert layers[0].filename == "unknown"

    def test_handles_empty_layers(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        layers = cache.parse_layers({"layers": []})
        assert layers == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past-store/tests/test_cache.py -v`
Expected: FAIL — `LayerInfo` and `parse_layers` don't exist.

- [ ] **Step 3: Implement LayerInfo and parse_layers**

Add to `cache.py` after the imports:

```python
from dataclasses import dataclass


@dataclass
class LayerInfo:
    """Metadata for a single OCI layer."""
    digest: str       # "sha256:abc123..."
    filename: str     # "dprr.ttl" or "_schema.yaml"
    size: int         # bytes
    is_sidecar: bool  # True if filename starts with "_"
```

Add method to `ArtifactCache`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past-store/tests/test_cache.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-store/linked_past_store/cache.py packages/linked-past-store/tests/test_cache.py
git commit -m "feat: add LayerInfo dataclass and manifest parsing to ArtifactCache"
```

---

### Task 2: Manifest fetch and caching

**Files:**
- Modify: `packages/linked-past-store/linked_past_store/cache.py`
- Modify: `packages/linked-past-store/tests/test_cache.py`

- [ ] **Step 1: Write failing tests for manifest fetch/cache**

Add to `test_cache.py`:

```python
from unittest.mock import patch


class TestFetchManifest:
    def test_caches_manifest_json(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        manifest_json = json.dumps(SAMPLE_MANIFEST)

        with patch("linked_past_store.cache._fetch_manifest_json", return_value=manifest_json):
            result = cache.fetch_manifest("ghcr.io/test/dataset:v1")

        assert result == SAMPLE_MANIFEST
        # Should be cached on disk
        cached_path = cache._manifests_dir / "ghcr.io/test/dataset/v1.json"
        assert cached_path.exists()
        assert json.loads(cached_path.read_text()) == SAMPLE_MANIFEST

    def test_returns_cached_manifest(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        # Pre-populate cache
        cached_path = cache._manifests_dir / "ghcr.io/test/dataset/v1.json"
        cached_path.parent.mkdir(parents=True, exist_ok=True)
        cached_path.write_text(json.dumps(SAMPLE_MANIFEST))

        result = cache.get_manifest("ghcr.io/test/dataset:v1")
        assert result == SAMPLE_MANIFEST

    def test_get_manifest_returns_none_if_not_cached(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        assert cache.get_manifest("ghcr.io/test/nonexistent:v1") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past-store/tests/test_cache.py::TestFetchManifest -v`
Expected: FAIL.

- [ ] **Step 3: Implement manifest fetch and caching**

Add module-level function to `cache.py`:

```python
def _fetch_manifest_json(ref: str) -> str | None:
    """Fetch raw manifest JSON from OCI registry."""
    try:
        result = subprocess.run(
            ["oras", "manifest", "fetch", ref],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except Exception as e:
        logger.debug("Failed to fetch manifest for %s: %s", ref, e)
        return None
```

Add methods to `ArtifactCache`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past-store/tests/test_cache.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-store/linked_past_store/cache.py packages/linked-past-store/tests/test_cache.py
git commit -m "feat: add manifest fetch and local caching to ArtifactCache"
```

---

### Task 3: Per-layer cache storage

**Files:**
- Modify: `packages/linked-past-store/linked_past_store/cache.py`
- Modify: `packages/linked-past-store/tests/test_cache.py`

- [ ] **Step 1: Write failing tests for layer storage**

Add to `test_cache.py`:

```python
class TestLayerCache:
    def test_has_layer_false_when_missing(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        assert not cache.has_layer("sha256:nonexistent")

    def test_has_layer_true_when_present(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        layer_dir = cache._layers_dir / "abc123"
        layer_dir.mkdir(parents=True)
        (layer_dir / "data.ttl").write_text("content")
        assert cache.has_layer("sha256:abc123")

    def test_put_layer_stores_file(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        src = tmp_path / "data.ttl"
        src.write_text("@prefix ex: <http://example.org/> .\n")
        cache.put_layer("sha256:abc123", "data.ttl", src)
        layer_path = cache._layers_dir / "abc123" / "data.ttl"
        assert layer_path.exists()
        assert layer_path.read_text() == src.read_text()

    def test_get_layer_path(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        layer_dir = cache._layers_dir / "abc123"
        layer_dir.mkdir(parents=True)
        (layer_dir / "data.ttl").write_text("content")
        result = cache.get_layer_path("sha256:abc123", "data.ttl")
        assert result is not None
        assert result.name == "data.ttl"

    def test_get_layer_path_none_when_missing(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        assert cache.get_layer_path("sha256:nonexistent", "data.ttl") is None

    def test_assemble_blob_dir_creates_symlinks(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        # Pre-populate layer cache
        for digest, filename, content in [
            ("sha256:aaa", "data.ttl", "rdf content"),
            ("sha256:bbb", "_void.ttl", "void content"),
        ]:
            cache.put_layer(digest, filename, _write_tmp(tmp_path, filename, content))

        layers = [
            LayerInfo("sha256:aaa", "data.ttl", 100, False),
            LayerInfo("sha256:bbb", "_void.ttl", 50, True),
        ]
        blob_dir = cache.assemble_blob_dir("sha256:manifest_digest", layers)

        assert (blob_dir / "data.ttl").exists()
        assert (blob_dir / "_void.ttl").exists()
        assert (blob_dir / "data.ttl").read_text() == "rdf content"
        assert (blob_dir / "_void.ttl").read_text() == "void content"


def _write_tmp(tmp_path, filename, content):
    """Helper: write a temp file and return its path."""
    p = tmp_path / "tmp_files" / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past-store/tests/test_cache.py::TestLayerCache -v`
Expected: FAIL.

- [ ] **Step 3: Implement layer cache storage**

Add `_layers_dir` property to `ArtifactCache.__init__`:

```python
    def __init__(self, cache_dir: Path | None = None):
        self._cache_dir = cache_dir or _default_cache_dir()
        self._manifests_dir = self._cache_dir / "manifests"
        self._blobs_dir = self._cache_dir / "blobs" / "sha256"
        self._layers_dir = self._cache_dir / "layers"
        self._gc_path = self._cache_dir / "gc.json"
```

Add methods to `ArtifactCache`:

```python
    def has_layer(self, digest: str) -> bool:
        """Check if a layer blob exists in the layer cache."""
        layer_dir = self._layers_dir / digest.replace("sha256:", "")
        return layer_dir.exists() and any(layer_dir.iterdir())

    def put_layer(self, digest: str, filename: str, src_path: Path) -> None:
        """Store a file in the per-layer cache."""
        layer_dir = self._layers_dir / digest.replace("sha256:", "")
        layer_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(src_path, layer_dir / filename)

    def get_layer_path(self, digest: str, filename: str) -> Path | None:
        """Get the path to a cached layer file, or None."""
        layer_path = self._layers_dir / digest.replace("sha256:", "") / filename
        if layer_path.exists():
            return layer_path
        return None

    def assemble_blob_dir(self, manifest_digest: str, layers: list[LayerInfo]) -> Path:
        """Assemble a blob directory from cached layers using symlinks (copy fallback)."""
        blob_dir = self._blobs_dir / manifest_digest.replace("sha256:", "")
        blob_dir.mkdir(parents=True, exist_ok=True)

        for layer in layers:
            src = self.get_layer_path(layer.digest, layer.filename)
            if src is None:
                raise FileNotFoundError(f"Layer {layer.digest} ({layer.filename}) not in cache")
            dst = blob_dir / layer.filename
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            try:
                dst.symlink_to(src.resolve())
            except OSError:
                # Symlinks not supported (some Windows configs) — fall back to copy
                import shutil
                shutil.copy2(src, dst)

        return blob_dir
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past-store/tests/test_cache.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-store/linked_past_store/cache.py packages/linked-past-store/tests/test_cache.py
git commit -m "feat: add per-layer blob cache storage with symlink assembly"
```

---

### Task 4: Layer-aware pull

**Files:**
- Modify: `packages/linked-past-store/linked_past_store/cache.py`
- Modify: `packages/linked-past-store/tests/test_cache.py`

- [ ] **Step 1: Write failing test for layer-aware pull**

Add to `test_cache.py`:

```python
class TestDigestVerification:
    def test_verify_correct_digest(self, tmp_path):
        import hashlib
        from linked_past_store.cache import _verify_digest
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        expected = "sha256:" + hashlib.sha256(b"hello world").hexdigest()
        assert _verify_digest(f, expected)

    def test_verify_wrong_digest(self, tmp_path):
        from linked_past_store.cache import _verify_digest
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        assert not _verify_digest(f, "sha256:0000000000000000000000000000000000000000000000000000000000000000")


class TestAssembleBlobDirSymlinkFallback:
    def test_falls_back_to_copy_when_symlink_fails(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        cache.put_layer("sha256:aaa", "data.ttl", _write_tmp(tmp_path, "data.ttl", "content"))
        layers = [LayerInfo("sha256:aaa", "data.ttl", 100, False)]

        with patch("pathlib.Path.symlink_to", side_effect=OSError("not supported")):
            blob_dir = cache.assemble_blob_dir("sha256:manifest1", layers)

        assert (blob_dir / "data.ttl").exists()
        assert (blob_dir / "data.ttl").read_text() == "content"
        assert not (blob_dir / "data.ttl").is_symlink()  # copy, not symlink


class TestLayerAwarePull:
    def test_skips_cached_layers(self, tmp_path):
        """When one layer is already cached, only the missing layer is downloaded."""
        cache = ArtifactCache(tmp_path / "cache")

        # Pre-populate one layer in cache
        cache.put_layer("sha256:aaa111", "dprr.ttl",
                        _write_tmp(tmp_path, "dprr.ttl", "existing rdf"))

        # Mock manifest fetch
        manifest_json = json.dumps(SAMPLE_MANIFEST)

        download_calls = []

        def fake_blob_fetch(ref, digest, outpath):
            download_calls.append(digest)
            Path(outpath).write_text(f"content of {digest}")

        with (
            patch("linked_past_store.cache._fetch_manifest_json", return_value=manifest_json),
            patch("linked_past_store.cache._resolve_digest", return_value="sha256:manifest_new"),
            patch.object(cache, "_download_layer", side_effect=fake_blob_fetch),
        ):
            blob_dir = cache.pull("ghcr.io/test/dataset:v1", force=True)

        # dprr.ttl was cached — should NOT be in download_calls
        assert "sha256:aaa111" not in download_calls
        # _void.ttl and _schema.yaml were missing — should be downloaded
        assert "sha256:bbb222" in download_calls
        assert "sha256:ccc333" in download_calls
        # Assembled blob dir has all files
        assert (blob_dir / "dprr.ttl").exists()
        assert (blob_dir / "_void.ttl").exists()
        assert (blob_dir / "_schema.yaml").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past-store/tests/test_cache.py::TestLayerAwarePull -v`
Expected: FAIL.

- [ ] **Step 3: Implement layer-aware pull and _download_layer**

Add method to `ArtifactCache`:

```python
    def _download_layer(self, ref: str, digest: str, outpath: str) -> None:
        """Download a single layer blob by digest and verify its content hash."""
        # oras blob fetch uses repo@digest syntax (strip tag from ref)
        repo = ref.rsplit(":", 1)[0]
        try:
            subprocess.run(
                ["oras", "blob", "fetch", f"{repo}@{digest}", "--output", outpath],
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning("oras blob fetch failed for %s: %s", digest[:20], e)
            raise

        # Verify downloaded content matches declared digest
        if not _verify_digest(Path(outpath), digest):
            Path(outpath).unlink(missing_ok=True)
            raise RuntimeError(
                f"Digest verification failed for {digest}: "
                f"downloaded content does not match expected hash"
            )
```

Add module-level digest verification function to `cache.py`:

```python
def _verify_digest(path: Path, expected: str) -> bool:
    """Verify a file's SHA-256 digest matches the expected OCI digest."""
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    actual = f"sha256:{h.hexdigest()}"
    return actual == expected
```

Replace the existing `pull()` method body with the layer-aware version:

```python
    def pull(self, ref: str, force: bool = False) -> Path:
        """Pull an artifact, using per-layer cache when possible.

        Args:
            ref: OCI reference (e.g., "ghcr.io/myorg/dataset:v1.0")
            force: If True, bypass cache and re-download all layers

        Returns:
            Path to the blob directory containing artifact files
        """
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

            # Download only missing layers
            for layer in layers:
                if not self.has_layer(layer.digest):
                    logger.info("Downloading layer %s (%s, %d bytes)",
                                layer.filename, layer.digest[:20], layer.size)
                    import tempfile
                    tmp_dir = self._cache_dir / "tmp"
                    tmp_dir.mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile(
                        dir=tmp_dir, suffix=f"_{layer.filename}", delete=False,
                    ) as tmp_file:
                        tmp_path = Path(tmp_file.name)
                    try:
                        self._download_layer(ref, layer.digest, str(tmp_path))
                        self.put_layer(layer.digest, layer.filename, tmp_path)
                    finally:
                        tmp_path.unlink(missing_ok=True)
                else:
                    logger.info("Layer cached: %s (%s)", layer.filename, layer.digest[:20])

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past-store/tests/test_cache.py -v && uv run pytest packages/linked-past-store/tests/test_pull.py -v`
Expected: All PASS (including existing pull tests — backward compatible).

- [ ] **Step 5: Run lint**

Run: `uv run ruff check packages/linked-past-store/`
Expected: Clean.

- [ ] **Step 6: Commit**

```bash
git add packages/linked-past-store/linked_past_store/cache.py packages/linked-past-store/tests/test_cache.py
git commit -m "feat: layer-aware pull with per-blob download skipping"
```

---

### Task 5: Smart store invalidation

**Files:**
- Modify: `packages/linked-past-store/linked_past_store/pull.py`
- Modify: `packages/linked-past-store/tests/test_pull.py`

- [ ] **Step 1: Write failing tests for smart invalidation**

Add to `test_pull.py`:

```python
from linked_past_store.pull import _classify_changes


def test_classify_changes_data_changed():
    old_layers = {"dprr.ttl": "sha256:aaa", "_void.ttl": "sha256:bbb"}
    new_layers = {"dprr.ttl": "sha256:xxx", "_void.ttl": "sha256:bbb"}  # data changed
    result = _classify_changes(old_layers, new_layers)
    assert result == "data"


def test_classify_changes_sidecar_only():
    old_layers = {"dprr.ttl": "sha256:aaa", "_void.ttl": "sha256:bbb"}
    new_layers = {"dprr.ttl": "sha256:aaa", "_void.ttl": "sha256:xxx"}  # only sidecar changed
    result = _classify_changes(old_layers, new_layers)
    assert result == "sidecar"


def test_classify_changes_nothing():
    old_layers = {"dprr.ttl": "sha256:aaa", "_void.ttl": "sha256:bbb"}
    new_layers = {"dprr.ttl": "sha256:aaa", "_void.ttl": "sha256:bbb"}
    result = _classify_changes(old_layers, new_layers)
    assert result == "none"


def test_classify_changes_new_data_file():
    old_layers = {"dprr.ttl": "sha256:aaa"}
    new_layers = {"dprr.ttl": "sha256:aaa", "extra.ttl": "sha256:ccc"}  # new data file
    result = _classify_changes(old_layers, new_layers)
    assert result == "data"


def test_classify_changes_removed_data_file():
    old_layers = {"dprr.ttl": "sha256:aaa", "extra.ttl": "sha256:bbb"}
    new_layers = {"dprr.ttl": "sha256:aaa"}  # extra.ttl removed
    result = _classify_changes(old_layers, new_layers)
    assert result == "data"


def test_classify_changes_new_sidecar():
    old_layers = {"dprr.ttl": "sha256:aaa"}
    new_layers = {"dprr.ttl": "sha256:aaa", "_schema.yaml": "sha256:ccc"}  # new sidecar
    result = _classify_changes(old_layers, new_layers)
    assert result == "sidecar"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past-store/tests/test_pull.py::test_classify_changes_data_changed -v`
Expected: FAIL — `_classify_changes` not found.

- [ ] **Step 3: Implement _classify_changes and update pull_for_dataset**

Add to `pull.py`:

```python
def _classify_changes(
    old_layers: dict[str, str],
    new_layers: dict[str, str],
) -> str:
    """Classify what changed between two manifest layer sets.

    Args:
        old_layers: {filename: digest} from old manifest
        new_layers: {filename: digest} from new manifest

    Returns:
        "data" if any non-sidecar file changed or was added/removed,
        "sidecar" if only _-prefixed files changed,
        "none" if nothing changed.
    """
    all_files = set(old_layers) | set(new_layers)
    data_changed = False
    sidecar_changed = False

    for filename in all_files:
        old_digest = old_layers.get(filename)
        new_digest = new_layers.get(filename)
        if old_digest != new_digest:
            if filename.startswith("_"):
                sidecar_changed = True
            else:
                data_changed = True

    if data_changed:
        return "data"
    if sidecar_changed:
        return "sidecar"
    return "none"
```

Update `pull_for_dataset` to use smart invalidation:

```python
def pull_for_dataset(
    dataset: str,
    output_dir: str | Path,
    version: str = "latest",
    registry: str | None = None,
    force: bool = False,
) -> Path:
    """Pull a dataset by name from the configured registry.

    Uses per-layer caching. Only invalidates the Oxigraph store when
    data files change; sidecar-only changes just copy new sidecars.
    """
    registry = registry or os.environ.get(
        "LINKED_PAST_REGISTRY", "ghcr.io/gillisandrew/linked-past"
    )
    ref = f"{registry}/{dataset}:{version}"
    output_dir = Path(output_dir)

    cache = ArtifactCache()

    # Capture old manifest before pulling
    old_manifest = cache.get_manifest(ref)
    old_digest = cache.digest_for(ref)

    result = pull_dataset(ref, output_dir, force=force)

    new_digest = cache.digest_for(ref)
    new_manifest = cache.get_manifest(ref)

    # If digest didn't change, nothing to do
    if old_digest and new_digest and old_digest == new_digest:
        return result

    # Compare layer digests to decide what to invalidate
    if old_manifest and new_manifest:
        old_layers = {
            l.filename: l.digest
            for l in cache.parse_layers(old_manifest)
        }
        new_layers = {
            l.filename: l.digest
            for l in cache.parse_layers(new_manifest)
        }
        change_type = _classify_changes(old_layers, new_layers)

        store_path = output_dir / "store"
        if change_type == "data":
            if store_path.exists():
                shutil.rmtree(store_path)
                logger.info("Store invalidated for %s (data files changed)", dataset)
        elif change_type == "sidecar":
            # Copy only changed sidecars — store untouched
            for layer in cache.parse_layers(new_manifest):
                if layer.is_sidecar and old_layers.get(layer.filename) != layer.digest:
                    src = cache.get_layer_path(layer.digest, layer.filename)
                    if src:
                        shutil.copy2(src, output_dir / layer.filename)
                        logger.info("Updated sidecar %s for %s", layer.filename, dataset)
        # "none" → nothing to do
    elif old_digest and new_digest and old_digest != new_digest:
        # No manifests available — fall back to old behavior
        store_path = output_dir / "store"
        if store_path.exists():
            shutil.rmtree(store_path)
            logger.info("Store invalidated for %s (digest changed, no manifest for comparison)",
                        dataset)

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past-store/tests/test_pull.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-store/linked_past_store/pull.py packages/linked-past-store/tests/test_pull.py
git commit -m "feat: smart store invalidation — sidecars skip Oxigraph rebuild"
```

---

### Task 6: Layer GC and CLI update

**Files:**
- Modify: `packages/linked-past-store/linked_past_store/cache.py`
- Modify: `packages/linked-past-store/linked_past_store/cli.py`
- Modify: `packages/linked-past-store/tests/test_cache.py`

- [ ] **Step 1: Write failing tests for layer GC**

Add to `test_cache.py`:

```python
class TestLayerGC:
    def test_gc_removes_orphaned_layers(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")

        # Create two layers
        cache.put_layer("sha256:used", "data.ttl", _write_tmp(tmp_path, "data.ttl", "used"))
        cache.put_layer("sha256:orphan", "old.ttl", _write_tmp(tmp_path, "old.ttl", "orphan"))

        # Assemble a blob dir referencing only the first layer
        layers = [LayerInfo("sha256:used", "data.ttl", 100, False)]
        cache.assemble_blob_dir("sha256:manifest1", layers)

        # GC with max_age=0 should remove orphaned layer
        removed = cache.gc(max_age_days=0)

        assert cache.has_layer("sha256:used")  # referenced → kept
        assert not cache.has_layer("sha256:orphan")  # orphaned → removed
        assert removed >= 1

    def test_gc_preserves_recently_accessed_layers(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        cache.put_layer("sha256:recent", "data.ttl", _write_tmp(tmp_path, "data.ttl", "content"))

        # Touch it (put_layer already does this implicitly via _touch_layer)
        # GC with max_age=30 should keep it
        removed = cache.gc(max_age_days=30)
        assert cache.has_layer("sha256:recent")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past-store/tests/test_cache.py::TestLayerGC -v`
Expected: FAIL.

- [ ] **Step 3: Implement layer-aware GC**

Update `_touch` to also track layer access. Add `_touch_layer` method:

```python
    def _touch_layer(self, digest: str) -> None:
        gc = self._load_gc()
        gc.setdefault("layers", {})[digest] = datetime.now(timezone.utc).isoformat()
        self._save_gc(gc)
```

Update `put_layer` to call `_touch_layer`:

```python
    def put_layer(self, digest: str, filename: str, src_path: Path) -> None:
        """Store a file in the per-layer cache."""
        layer_dir = self._layers_dir / digest.replace("sha256:", "")
        layer_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(src_path, layer_dir / filename)
        self._touch_layer(digest)
```

Update `assemble_blob_dir` to record layer references in GC data:

```python
    def assemble_blob_dir(self, manifest_digest: str, layers: list[LayerInfo]) -> Path:
        """Assemble a blob directory from cached layers using symlinks (copy fallback)."""
        blob_dir = self._blobs_dir / manifest_digest.replace("sha256:", "")
        blob_dir.mkdir(parents=True, exist_ok=True)

        for layer in layers:
            src = self.get_layer_path(layer.digest, layer.filename)
            if src is None:
                raise FileNotFoundError(f"Layer {layer.digest} ({layer.filename}) not in cache")
            dst = blob_dir / layer.filename
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            try:
                dst.symlink_to(src.resolve())
            except OSError:
                import shutil
                shutil.copy2(src, dst)

        # Record layer references for GC
        gc = self._load_gc()
        gc.setdefault("manifest_layers", {})[manifest_digest] = [l.digest for l in layers]
        self._save_gc(gc)

        return blob_dir
```

Update `gc()` to include layer cleanup:

```python
    def gc(self, max_age_days: int = 30) -> int:
        """Remove cached blobs and orphaned layers not accessed in max_age_days."""
        gc_data = self._load_gc()
        now = datetime.now(timezone.utc)
        removed = 0

        # Phase 1: GC manifest blobs (existing behavior)
        surviving_manifests = set()
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

            import shutil
            shutil.rmtree(digest_dir, ignore_errors=True)
            gc_data.pop(digest, None)
            gc_data.get("manifest_layers", {}).pop(digest, None)
            removed += 1
            logger.info("GC: removed manifest blob %s", digest[:20])

        # Phase 2: GC orphaned layers
        referenced_layers = set()
        for manifest_digest in surviving_manifests:
            layer_digests = gc_data.get("manifest_layers", {}).get(manifest_digest, [])
            referenced_layers.update(layer_digests)

        layer_access = gc_data.get("layers", {})
        for layer_dir in list(self._layers_dir.iterdir()) if self._layers_dir.exists() else []:
            layer_digest = f"sha256:{layer_dir.name}"
            if layer_digest in referenced_layers:
                continue  # Referenced by a surviving manifest
            last_access = layer_access.get(layer_digest)
            if last_access:
                try:
                    last_dt = datetime.fromisoformat(last_access)
                    if (now - last_dt).days <= max_age_days:
                        continue
                except ValueError:
                    pass

            import shutil
            shutil.rmtree(layer_dir, ignore_errors=True)
            layer_access.pop(layer_digest, None)
            removed += 1
            logger.info("GC: removed orphaned layer %s", layer_digest[:20])

        self._save_gc(gc_data)
        return removed
```

- [ ] **Step 4: Update CLI cache clear to wipe layers**

In `cli.py`, update `cmd_cache_clear`:

```python
def cmd_cache_clear(args):
    import shutil

    from linked_past_store.cache import ArtifactCache

    cache = ArtifactCache()
    if cache._blobs_dir.exists():
        shutil.rmtree(cache._blobs_dir)
    if cache._layers_dir.exists():
        shutil.rmtree(cache._layers_dir)
    if cache._manifests_dir.exists():
        shutil.rmtree(cache._manifests_dir)
    if cache._gc_path.exists():
        cache._gc_path.unlink()
    print("Cache cleared.")
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest packages/linked-past-store/ -v && uv run ruff check packages/linked-past-store/`
Expected: All PASS, lint clean.

- [ ] **Step 6: Commit**

```bash
git add packages/linked-past-store/linked_past_store/cache.py packages/linked-past-store/linked_past_store/cli.py packages/linked-past-store/tests/test_cache.py
git commit -m "feat: layer-aware GC with reference counting, CLI cache clear includes layers"
```
