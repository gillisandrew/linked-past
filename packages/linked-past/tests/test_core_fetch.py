from pathlib import Path
from unittest.mock import MagicMock, patch

from linked_past.core.fetch import artifact_ref, default_registry, pull_artifact


def test_artifact_ref():
    ref = artifact_ref("dprr", "1.3.0")
    assert "dprr" in ref
    assert "1.3.0" in ref


def test_artifact_ref_latest():
    ref = artifact_ref("pleiades")
    assert "latest" in ref


def test_default_registry():
    reg = default_registry()
    assert "ghcr.io" in reg


def test_pull_artifact_downloads(tmp_path):
    cache_dir = tmp_path / "cache"

    def fake_pull(target, outdir):
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        ttl = outdir / "dprr.ttl"
        ttl.write_text("@prefix ex: <http://example.org/> .\n")
        return [str(ttl)]

    with (
        patch("linked_past_store.cache.oras.client.OrasClient") as MockClient,
        patch("linked_past_store.cache._default_cache_dir", return_value=cache_dir),
        patch("linked_past_store.cache._resolve_digest", return_value="sha256:test123"),
    ):
        mock = MagicMock()
        MockClient.return_value = mock
        mock.pull.side_effect = fake_pull

        result = pull_artifact("dprr", tmp_path / "output", version="1.0.0", force=True)

    assert result.suffix == ".ttl"
    assert result.exists()
