"""Tests for OCI pull operations with caching."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from linked_past_store.cache import ArtifactCache
from linked_past_store.pull import pull_dataset


def test_pull_dataset_cache_miss_downloads(tmp_path):
    """On cache miss, downloads from OCI and caches."""
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "output"

    def fake_pull(target, outdir):
        """Simulate oras pull by creating a file in outdir."""
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        ttl = outdir / "data.ttl"
        ttl.write_text("@prefix ex: <http://example.org/> .\n")
        return [str(ttl)]

    with (
        patch("linked_past_store.cache.oras.client.OrasClient") as MockClient,
        patch("linked_past_store.cache._default_cache_dir", return_value=cache_dir),
        patch("linked_past_store.cache._resolve_digest", return_value="sha256:abc123"),
    ):
        mock = MagicMock()
        MockClient.return_value = mock
        mock.pull.side_effect = fake_pull

        result = pull_dataset("ghcr.io/test/dataset:v1", output_dir, force=True)

    assert result.suffix == ".ttl"
    assert result.exists()
    assert "data.ttl" in result.name


def test_pull_dataset_raises_if_no_ttl(tmp_path):
    """Raises RuntimeError if no .ttl in pulled artifact."""
    cache_dir = tmp_path / "cache"

    def fake_pull(target, outdir):
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        json_file = outdir / "data.json"
        json_file.write_text("{}")
        return [str(json_file)]

    with (
        patch("linked_past_store.cache.oras.client.OrasClient") as MockClient,
        patch("linked_past_store.cache._default_cache_dir", return_value=cache_dir),
        patch("linked_past_store.cache._resolve_digest", return_value="sha256:abc123"),
    ):
        mock = MagicMock()
        MockClient.return_value = mock
        mock.pull.side_effect = fake_pull

        try:
            pull_dataset("ghcr.io/test/dataset:v1", tmp_path / "output", force=True)
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "No .ttl file" in str(e)


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


def test_pull_dataset_cache_hit_skips_download(tmp_path):
    """On cache hit, returns cached file without downloading."""
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "output"

    # Pre-populate cache
    cache = ArtifactCache(cache_dir)
    blob_dir = cache._blobs_dir / "abc123"
    blob_dir.mkdir(parents=True)
    (blob_dir / "data.ttl").write_text("@prefix ex: <http://example.org/> .\n")
    cache.put("ghcr.io/test/dataset:v1", "sha256:abc123", blob_dir)

    with patch("linked_past_store.cache._default_cache_dir", return_value=cache_dir):
        # Should not call oras at all
        result = pull_dataset("ghcr.io/test/dataset:v1", output_dir)

    assert result.suffix == ".ttl"
    assert result.exists()
