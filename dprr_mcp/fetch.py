"""Download and extract the DPRR data tarball."""

import logging
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DATA_URL = "https://github.com/gillisandrew/dprr-mcp/releases/latest/download/dprr-data.tar.gz"


def fetch_data(data_dir: Path, url: str | None = None) -> Path:
    """Download the DPRR data tarball and extract dprr.ttl to data_dir.

    Args:
        data_dir: Directory to extract dprr.ttl into.
        url: Override URL. Falls back to DPRR_DATA_URL envvar, then DEFAULT_DATA_URL.

    Returns:
        Path to the extracted dprr.ttl file.

    Raises:
        RuntimeError: If download fails or tarball doesn't contain dprr.ttl.
    """
    resolved_url = url or os.environ.get("DPRR_DATA_URL", DEFAULT_DATA_URL)
    logger.info("Downloading DPRR data from %s", resolved_url)
    print(f"Downloading DPRR data from {resolved_url} ...", file=sys.stderr)

    try:
        tmp_path, _ = urllib.request.urlretrieve(resolved_url)
    except OSError as e:
        raise RuntimeError(f"Failed to download data from {resolved_url}: {e}") from e

    try:
        with tarfile.open(tmp_path, "r:gz") as tar:
            members = tar.getnames()
            if "dprr.ttl" not in members:
                raise RuntimeError(
                    f"Tarball does not contain dprr.ttl. Found: {members}"
                )
            tar.extract("dprr.ttl", path=str(data_dir), filter="data")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    result = data_dir / "dprr.ttl"
    print(f"Extracted dprr.ttl to {result}", file=sys.stderr)
    return result
