"""Push RDF datasets to OCI registries with scholarly annotations."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import oras.client

logger = logging.getLogger(__name__)


def push_dataset(
    ref: str,
    path: str | Path | list[str | Path],
    annotations: dict[str, str] | None = None,
    media_type: str = "application/x-turtle",
) -> str:
    """Push RDF file(s) to an OCI registry as an artifact.

    Args:
        ref: OCI reference (e.g., "ghcr.io/myorg/dataset:v1.0")
        path: Path(s) to RDF file(s) to push. Single path or list of paths.
        annotations: OCI manifest annotations (license, citation, etc.)
        media_type: MIME type for the artifact layers

    Returns:
        The digest of the pushed artifact (sha256:...)
    """
    # Normalize to list
    if isinstance(path, (str, Path)):
        paths = [Path(path)]
    else:
        paths = [Path(p) for p in path]

    for p in paths:
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")

    # oras-py expects "path:mediaType" strings
    files = [f"{p}:{media_type}" for p in paths]

    logger.info("Pushing %d file(s) to %s", len(paths), ref)
    client = oras.client.OrasClient()
    response = client.push(
        target=ref,
        files=files,
        manifest_annotations=annotations or {},
        disable_path_validation=True,
    )

    digest = response.headers.get("Docker-Content-Digest", "")
    if digest:
        logger.info("Pushed %s (digest: %s)", ref, digest)
    else:
        logger.info("Pushed %s", ref)
    return digest


def tag_artifact(ref: str, new_tag: str) -> None:
    """Add a tag to an existing OCI artifact.

    Args:
        ref: Existing OCI reference (e.g., "ghcr.io/myorg/dataset:v1.0")
        new_tag: New tag to add (e.g., "latest")
    """
    subprocess.run(["oras", "tag", ref, new_tag], check=True)
    logger.info("Tagged %s as %s", ref, new_tag)
