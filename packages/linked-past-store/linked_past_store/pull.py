"""Pull RDF datasets from OCI registries with local caching."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from linked_past_store.cache import ArtifactCache

__all__ = ["pull_dataset", "pull_for_dataset"]

logger = logging.getLogger(__name__)


def pull_dataset(
    ref: str,
    output_dir: str | Path,
    force: bool = False,
) -> Path:
    """Pull an RDF dataset artifact from an OCI registry.

    Uses a content-addressable local cache. Repeated pulls of the same
    digest are instant. Use force=True to bypass cache.

    Args:
        ref: OCI reference (e.g., "ghcr.io/myorg/dataset:v1.0")
        output_dir: Directory to copy files into
        force: Bypass cache and re-download from registry

    Returns:
        Path to the primary .ttl file in output_dir
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cache = ArtifactCache()
    blob_dir = cache.pull(ref, force=force)

    # Copy from cache to output directory
    ttl_files = cache.find_ttl(blob_dir)
    if not ttl_files:
        raise RuntimeError(f"No .ttl file found in artifact {ref}")

    copied = []
    for src in ttl_files:
        dst = output_dir / src.name
        if dst != src:
            shutil.copy2(src, dst)
        copied.append(dst)

    logger.info("Pulled %s → %s (%d files)", ref, output_dir, len(copied))
    return copied[0]


def pull_for_dataset(
    dataset: str,
    output_dir: str | Path,
    version: str = "latest",
    registry: str | None = None,
    force: bool = False,
) -> Path:
    """Pull a dataset by name from the configured registry.

    If the upstream digest has changed since the last pull, the local
    Oxigraph store is invalidated (deleted) so it gets rebuilt on next init.

    Args:
        dataset: Dataset name (e.g., "dprr", "pleiades")
        output_dir: Directory to copy files into
        version: OCI tag (default: "latest")
        registry: Override registry (default: LINKED_PAST_REGISTRY env or ghcr.io/gillisandrew/linked-past)
        force: Bypass cache, re-download from registry
    """
    registry = registry or os.environ.get(
        "LINKED_PAST_REGISTRY", "ghcr.io/gillisandrew/linked-past"
    )
    ref = f"{registry}/{dataset}:{version}"
    output_dir = Path(output_dir)

    # Check current digest before pulling
    cache = ArtifactCache()
    old_digest = cache.digest_for(ref)

    result = pull_dataset(ref, output_dir, force=force)

    # If digest changed, invalidate the Oxigraph store
    new_digest = cache.digest_for(ref)
    if old_digest and new_digest and old_digest != new_digest:
        store_path = output_dir / "store"
        if store_path.exists():
            shutil.rmtree(store_path)
            logger.info("Store invalidated for %s (digest changed: %s → %s)",
                        dataset, old_digest[:20], new_digest[:20])

    return result
