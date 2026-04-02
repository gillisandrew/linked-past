"""Tests for ArtifactCache layer-level caching."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from linked_past_store.cache import ArtifactCache, LayerInfo

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
        filenames = [layer.filename for layer in layers]
        assert "dprr.ttl" in filenames
        assert "_void.ttl" in filenames
        assert "_schema.yaml" in filenames

    def test_classifies_sidecars(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        layers = cache.parse_layers(SAMPLE_MANIFEST)
        by_name = {layer.filename: layer for layer in layers}
        assert not by_name["dprr.ttl"].is_sidecar
        assert by_name["_void.ttl"].is_sidecar
        assert by_name["_schema.yaml"].is_sidecar

    def test_extracts_digests_and_sizes(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        layers = cache.parse_layers(SAMPLE_MANIFEST)
        by_name = {layer.filename: layer for layer in layers}
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


# -- Helpers --


def _write_tmp(tmp_path: Path, filename: str, content: str) -> Path:
    """Write a temp file and return its path."""
    p = tmp_path / "tmp_files" / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# -- Task 3: Per-layer cache storage --


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


# -- Task 4: Layer-aware pull + digest verification --


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
        assert not _verify_digest(
            f,
            "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        )


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


class TestLayerGC:
    def test_gc_removes_orphaned_layers(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")

        # Create two layers
        cache.put_layer("sha256:used", "data.ttl", _write_tmp(tmp_path, "data.ttl", "used"))
        cache.put_layer("sha256:orphan", "old.ttl", _write_tmp(tmp_path, "old.ttl", "orphan"))

        # Assemble a blob dir referencing only the first layer
        layers = [LayerInfo("sha256:used", "data.ttl", 100, False)]
        cache.assemble_blob_dir("sha256:manifest1", layers)

        # Touch the manifest blob so it survives GC
        cache._touch("sha256:manifest1")

        # Backdate the orphan layer's access time so it's old enough to be evicted
        gc_data = cache._load_gc()
        old_time = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        gc_data.setdefault("layers", {})["sha256:orphan"] = old_time
        cache._save_gc(gc_data)

        # GC with max_age=30: orphan is 60 days old → removed; used is referenced → kept
        removed = cache.gc(max_age_days=30)

        assert cache.has_layer("sha256:used")        # referenced → kept
        assert not cache.has_layer("sha256:orphan")  # orphaned and old → removed
        assert removed >= 1

    def test_gc_preserves_recently_accessed_layers(self, tmp_path):
        cache = ArtifactCache(tmp_path / "cache")
        cache.put_layer("sha256:recent", "data.ttl", _write_tmp(tmp_path, "data.ttl", "content"))

        # put_layer calls _touch_layer, so access time is just now
        # GC with max_age=30 should keep it
        removed = cache.gc(max_age_days=30)
        assert cache.has_layer("sha256:recent")
        assert removed == 0


class TestLayerAwarePull:
    def test_skips_cached_layers(self, tmp_path):
        """When one layer is already cached, only the missing layers are downloaded."""
        cache = ArtifactCache(tmp_path / "cache")

        # Pre-populate one layer in cache
        cache.put_layer(
            "sha256:aaa111", "dprr.ttl", _write_tmp(tmp_path, "dprr.ttl", "existing rdf")
        )

        manifest_json = json.dumps(SAMPLE_MANIFEST)
        download_calls = []

        def fake_blob_fetch(ref, digest, outpath, **kwargs):
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
