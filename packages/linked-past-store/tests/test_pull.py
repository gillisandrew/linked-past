"""Tests for OCI pull operations."""

from unittest.mock import MagicMock, patch

from linked_past_store.pull import pull_dataset


def test_pull_dataset_returns_ttl_path(tmp_path):
    with patch("linked_past_store.pull.oras.client.OrasClient") as MockClient:
        mock = MagicMock()
        MockClient.return_value = mock
        ttl = tmp_path / "data.ttl"
        ttl.write_text("@prefix ex: <http://example.org/> .\n")
        mock.pull.return_value = [str(ttl)]

        result = pull_dataset("ghcr.io/test/dataset:v1", tmp_path)

        assert result == ttl
        mock.pull.assert_called_once()


def test_pull_dataset_raises_if_no_ttl(tmp_path):
    with patch("linked_past_store.pull.oras.client.OrasClient") as MockClient:
        mock = MagicMock()
        MockClient.return_value = mock
        mock.pull.return_value = [str(tmp_path / "data.json")]

        try:
            pull_dataset("ghcr.io/test/dataset:v1", tmp_path)
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "No .ttl file" in str(e)
