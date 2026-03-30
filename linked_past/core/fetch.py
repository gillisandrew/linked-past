"""ORAS-based dataset fetching from OCI registry."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import oras.client

logger = logging.getLogger(__name__)

_DEFAULT_REGISTRY = "ghcr.io/gillisandrew/linked-past"


def default_registry() -> str:
    return os.environ.get("LINKED_PAST_REGISTRY", _DEFAULT_REGISTRY)


def artifact_ref(dataset: str, version: str = "latest") -> str:
    registry = default_registry()
    return f"{registry}/{dataset}:{version}"


def pull_artifact(dataset: str, data_dir: Path, version: str = "latest") -> Path:
    legacy_url = os.environ.get(f"LINKED_PAST_{dataset.upper()}_URL")
    if legacy_url:
        return _fetch_legacy(legacy_url, data_dir, dataset)

    ref = artifact_ref(dataset, version)
    logger.info("Pulling %s to %s", ref, data_dir)

    client = oras.client.OrasClient()
    files = client.pull(target=ref, outdir=str(data_dir))

    ttl_files = [Path(f) for f in files if f.endswith(".ttl")]
    if not ttl_files:
        raise RuntimeError(f"No .ttl file found in artifact {ref}. Got: {files}")

    logger.info("Pulled %s (%d files)", ref, len(files))
    return ttl_files[0]


def _fetch_legacy(url: str, data_dir: Path, dataset: str) -> Path:
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
