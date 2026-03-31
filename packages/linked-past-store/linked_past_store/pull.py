"""Pull RDF datasets from OCI registries."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import oras.client

logger = logging.getLogger(__name__)


def pull_dataset(
    ref: str,
    output_dir: str | Path,
) -> Path:
    """Pull an RDF dataset artifact from an OCI registry.

    Args:
        ref: OCI reference (e.g., "ghcr.io/myorg/dataset:v1.0")
        output_dir: Directory to download files into

    Returns:
        Path to the primary .ttl file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Pulling %s to %s", ref, output_dir)
    client = oras.client.OrasClient()
    files = client.pull(target=ref, outdir=str(output_dir))

    ttl_files = [Path(f) for f in files if f.endswith(".ttl")]
    if not ttl_files:
        raise RuntimeError(f"No .ttl file found in artifact {ref}. Got: {files}")

    logger.info("Pulled %s (%d files)", ref, len(files))
    return ttl_files[0]


def pull_with_legacy_fallback(
    dataset: str,
    output_dir: str | Path,
    version: str = "latest",
    registry: str | None = None,
) -> Path:
    """Pull a dataset, falling back to a legacy URL if set via env var.

    Checks LINKED_PAST_{DATASET}_URL for a legacy HTTP download URL.
    Falls back to ORAS pull from the registry.
    """
    legacy_url = os.environ.get(f"LINKED_PAST_{dataset.upper()}_URL")
    if legacy_url:
        return _fetch_legacy(legacy_url, Path(output_dir), dataset)

    registry = registry or os.environ.get(
        "LINKED_PAST_REGISTRY", "ghcr.io/gillisandrew/linked-past"
    )
    ref = f"{registry}/{dataset}:{version}"
    return pull_dataset(ref, output_dir)


def _fetch_legacy(url: str, data_dir: Path, dataset: str) -> Path:
    """Legacy HTTP fetch for backwards compatibility."""
    import shutil
    import tarfile
    import urllib.request

    logger.info("Legacy fetch from %s", url)
    data_dir.mkdir(parents=True, exist_ok=True)

    tmp_path, _ = urllib.request.urlretrieve(url)
    try:
        if tarfile.is_tarfile(tmp_path):
            with tarfile.open(tmp_path, "r:gz") as tar:
                tar.extractall(path=str(data_dir), filter="data")
        else:
            dest = data_dir / f"{dataset}.ttl"
            shutil.copy2(tmp_path, dest)
            return dest
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    ttl_files = list(data_dir.glob("*.ttl"))
    if not ttl_files:
        raise RuntimeError(f"No .ttl file found after fetching {url}")
    return ttl_files[0]
