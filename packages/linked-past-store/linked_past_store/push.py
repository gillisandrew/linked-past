"""Push RDF datasets to OCI registries with scholarly annotations."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def push_dataset(
    ref: str,
    path: str | Path,
    annotations: dict[str, str] | None = None,
    media_type: str = "application/x-turtle",
) -> str:
    """Push an RDF file to an OCI registry as an artifact.

    Args:
        ref: OCI reference (e.g., "ghcr.io/myorg/dataset:v1.0")
        path: Path to the RDF file to push
        annotations: OCI manifest annotations (license, citation, etc.)
        media_type: MIME type for the artifact layer

    Returns:
        The digest of the pushed artifact (sha256:...)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    cmd = ["oras", "push", ref, f"{path.name}:{media_type}"]
    if annotations:
        for key, val in annotations.items():
            cmd.extend(["--annotation", f"{key}={val}"])

    logger.info("Pushing %s to %s", path.name, ref)
    result = subprocess.run(cmd, cwd=str(path.parent), capture_output=True, text=True, check=True)

    # Extract digest from output
    for line in result.stdout.splitlines():
        if line.startswith("Digest:"):
            digest = line.split(":", 1)[1].strip()
            logger.info("Pushed %s (digest: %s)", ref, digest)
            return digest

    return ""


def tag_artifact(ref: str, new_tag: str) -> None:
    """Add a tag to an existing OCI artifact.

    Args:
        ref: Existing OCI reference (e.g., "ghcr.io/myorg/dataset:v1.0")
        new_tag: New tag to add (e.g., "latest")
    """
    subprocess.run(["oras", "tag", ref, new_tag], check=True)
    logger.info("Tagged %s as %s", ref, new_tag)
