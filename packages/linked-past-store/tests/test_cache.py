"""Tests for ArtifactCache layer-level caching."""

import json
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
