import os
import tarfile
from pathlib import Path
from unittest.mock import patch

import pytest

from dprr_mcp.fetch import DEFAULT_DATA_URL, fetch_data


def _make_tarball(tmp_path: Path, filename: str = "dprr.ttl", content: str = "test data") -> Path:
    """Create a gzipped tarball containing a single file."""
    file_path = tmp_path / filename
    file_path.write_text(content)
    tarball_path = tmp_path / "data.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(file_path, arcname=filename)
    return tarball_path


def test_fetch_data_extracts_ttl(tmp_path):
    """fetch_data downloads and extracts dprr.ttl to data_dir."""
    tarball_path = _make_tarball(tmp_path, content="<s> <p> <o> .")
    data_dir = tmp_path / "output"
    data_dir.mkdir()

    with patch("dprr_mcp.fetch.urllib.request.urlretrieve") as mock_retrieve:
        mock_retrieve.return_value = (str(tarball_path), {})
        fetch_data(data_dir, url="https://example.com/data.tar.gz")

    assert (data_dir / "dprr.ttl").exists()
    assert (data_dir / "dprr.ttl").read_text() == "<s> <p> <o> ."


def test_fetch_data_missing_ttl_in_tarball(tmp_path):
    """fetch_data raises RuntimeError if tarball lacks dprr.ttl."""
    tarball_path = _make_tarball(tmp_path, filename="wrong.txt")
    data_dir = tmp_path / "output"
    data_dir.mkdir()

    with patch("dprr_mcp.fetch.urllib.request.urlretrieve") as mock_retrieve:
        mock_retrieve.return_value = (str(tarball_path), {})
        with pytest.raises(RuntimeError, match="dprr.ttl"):
            fetch_data(data_dir, url="https://example.com/data.tar.gz")


def test_fetch_data_url_from_envvar(tmp_path):
    """DPRR_DATA_URL overrides the default URL."""
    tarball_path = _make_tarball(tmp_path, content="env data")
    data_dir = tmp_path / "output"
    data_dir.mkdir()

    with patch.dict(os.environ, {"DPRR_DATA_URL": "https://custom.example.com/data.tar.gz"}):
        with patch("dprr_mcp.fetch.urllib.request.urlretrieve") as mock_retrieve:
            mock_retrieve.return_value = (str(tarball_path), {})
            fetch_data(data_dir)
            mock_retrieve.assert_called_once()
            call_url = mock_retrieve.call_args[0][0]
            assert call_url == "https://custom.example.com/data.tar.gz"


def test_fetch_data_default_url():
    """Default URL points to GitHub releases."""
    assert "github.com" in DEFAULT_DATA_URL
    assert "dprr-data.tar.gz" in DEFAULT_DATA_URL


def test_fetch_data_network_error(tmp_path):
    """fetch_data raises RuntimeError on download failure."""
    data_dir = tmp_path / "output"
    data_dir.mkdir()

    with patch("dprr_mcp.fetch.urllib.request.urlretrieve", side_effect=OSError("connection refused")):
        with pytest.raises(RuntimeError, match="Failed to download"):
            fetch_data(data_dir, url="https://example.com/data.tar.gz")
