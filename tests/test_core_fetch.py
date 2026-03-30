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


def test_pull_artifact_calls_oras(tmp_path):
    with patch("linked_past.core.fetch.oras.client.OrasClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance
        mock_instance.pull.return_value = [str(tmp_path / "data.ttl")]

        pull_artifact("dprr", tmp_path, version="1.0.0")
        mock_instance.pull.assert_called_once()


def test_pull_artifact_returns_path(tmp_path):
    with patch("linked_past.core.fetch.oras.client.OrasClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance
        ttl_file = tmp_path / "data.ttl"
        ttl_file.write_text("# empty turtle")
        mock_instance.pull.return_value = [str(ttl_file)]

        result = pull_artifact("dprr", tmp_path, version="1.0.0")
        assert result == ttl_file
