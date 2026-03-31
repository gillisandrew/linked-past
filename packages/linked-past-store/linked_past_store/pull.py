"""Pull RDF datasets from OCI registries with local caching."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from linked_past_store.cache import ArtifactCache

__all__ = ["pull_dataset", "pull_for_dataset", "_classify_changes"]

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

    # Copy ALL files from cache to output directory
    all_files = [f for f in blob_dir.iterdir() if f.is_file() or f.is_symlink()]
    if not all_files:
        raise RuntimeError(f"No files found in artifact {ref}")

    ttl_files = []
    for src in all_files:
        dst = output_dir / src.name
        if dst != src:
            shutil.copy2(src, dst, follow_symlinks=True)
        if src.suffix == ".ttl":
            ttl_files.append(dst)

    if not ttl_files:
        raise RuntimeError(f"No .ttl file found in artifact {ref}")

    logger.info("Pulled %s → %s (%d files)", ref, output_dir, len(all_files))
    return ttl_files[0]


def _classify_changes(
    old_layers: dict[str, str],
    new_layers: dict[str, str],
) -> str:
    """Classify what changed between two manifest layer sets.

    Args:
        old_layers: {filename: digest} from old manifest
        new_layers: {filename: digest} from new manifest

    Returns:
        "data" if any non-sidecar file changed or was added/removed,
        "sidecar" if only _-prefixed files changed,
        "none" if nothing changed.
    """
    all_files = set(old_layers) | set(new_layers)
    data_changed = False
    sidecar_changed = False

    for filename in all_files:
        old_digest = old_layers.get(filename)
        new_digest = new_layers.get(filename)
        if old_digest != new_digest:
            if filename.startswith("_"):
                sidecar_changed = True
            else:
                data_changed = True

    if data_changed:
        return "data"
    if sidecar_changed:
        return "sidecar"
    return "none"


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

    cache = ArtifactCache()

    # Capture old manifest before pulling
    old_manifest = cache.get_manifest(ref)
    old_digest = cache.digest_for(ref)

    result = pull_dataset(ref, output_dir, force=force)

    new_digest = cache.digest_for(ref)
    new_manifest = cache.get_manifest(ref)

    # If digest didn't change, nothing to do
    if old_digest and new_digest and old_digest == new_digest:
        return result

    # Compare layer digests to decide what to invalidate
    if old_manifest and new_manifest:
        old_layers = {
            layer.filename: layer.digest
            for layer in cache.parse_layers(old_manifest)
        }
        new_layers = {
            layer.filename: layer.digest
            for layer in cache.parse_layers(new_manifest)
        }
        change_type = _classify_changes(old_layers, new_layers)

        store_path = output_dir / "store"
        if change_type == "data":
            if store_path.exists():
                shutil.rmtree(store_path)
                logger.info("Store invalidated for %s (data files changed)", dataset)
        elif change_type == "sidecar":
            # Copy only changed sidecars — store untouched
            for layer in cache.parse_layers(new_manifest):
                if layer.is_sidecar and old_layers.get(layer.filename) != layer.digest:
                    src = cache.get_layer_path(layer.digest, layer.filename)
                    if src:
                        shutil.copy2(src, output_dir / layer.filename)
                        logger.info("Updated sidecar %s for %s", layer.filename, dataset)
        # "none" → nothing to do
    elif old_digest and new_digest and old_digest != new_digest:
        # No manifests available — fall back to old behavior
        store_path = output_dir / "store"
        if store_path.exists():
            shutil.rmtree(store_path)
            logger.info(
                "Store invalidated for %s (digest changed, no manifest for comparison)",
                dataset,
            )

    return result
