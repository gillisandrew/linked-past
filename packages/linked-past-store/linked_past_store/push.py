"""Push RDF datasets to OCI registries with scholarly annotations."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def push_dataset(
    ref: str,
    path: str | Path | list[str | Path],
    annotations: dict[str, str] | None = None,
    media_type: str = "application/x-turtle",
    void_path: str | Path | None = None,
) -> str:
    """Push RDF file(s) to an OCI registry as an artifact.

    Args:
        ref: OCI reference (e.g., "ghcr.io/myorg/dataset:v1.0")
        path: Path(s) to RDF file(s) to push. Single path or list of paths.
        annotations: OCI manifest annotations (license, citation, etc.)
        media_type: MIME type for the artifact layers
        void_path: Optional path to VoID description file (pushed as additional layer)

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

    if void_path:
        void_path = Path(void_path)
        if not void_path.exists():
            raise FileNotFoundError(f"VoID file not found: {void_path}")

    # oras push uses filenames relative to cwd — use absolute paths via
    # relative-to-cwd references. All files should be in the same directory;
    # if void_path is elsewhere, use its absolute path.
    cwd = paths[0].parent

    cmd = ["oras", "push", ref]
    for p in paths:
        cmd.append(f"{p.name}:{media_type}")
    if void_path:
        # If void_path is in the same dir, use name; otherwise use relative path from cwd
        try:
            rel = void_path.relative_to(cwd)
            cmd.append(f"{rel}:{media_type}")
        except ValueError:
            # Different directory — use absolute path
            cmd.append(f"{void_path.resolve()}:{media_type}")

    if annotations:
        for key, val in annotations.items():
            cmd.extend(["--annotation", f"{key}={val}"])

    logger.info("Pushing %d file(s) to %s", len(paths), ref)
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=True)

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
