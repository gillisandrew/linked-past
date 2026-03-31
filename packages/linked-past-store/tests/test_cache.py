"""Tests for ArtifactCache layer-level caching."""

import json
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
