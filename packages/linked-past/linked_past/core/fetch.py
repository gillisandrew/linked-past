"""Dataset fetching — delegates to linked-past-store subpackage."""

from __future__ import annotations

import os
from pathlib import Path

from linked_past_store.pull import pull_for_dataset

_DEFAULT_REGISTRY = "ghcr.io/gillisandrew/linked-past"


def default_registry() -> str:
    return os.environ.get("LINKED_PAST_REGISTRY", _DEFAULT_REGISTRY)


def artifact_ref(dataset: str, version: str = "latest") -> str:
    registry = default_registry()
    return f"{registry}/{dataset}:{version}"


def pull_artifact(dataset: str, data_dir: Path, version: str = "latest", force: bool = False) -> Path:
    return pull_for_dataset(dataset, data_dir, version, default_registry(), force=force)
