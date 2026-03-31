"""Validate a clean dataset: triple count regression check.

Schema diff is handled by clean_dataset.py (which has both old and new schemas
in memory before pushing). This script handles post-push validation only.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from linked_past_store import pull_dataset, verify_turtle

from scripts.pipeline_config import load_dataset_config


def diff_schemas(old: dict, new: dict) -> dict:
    """Compare two schema dicts (class_name -> {label, properties}).

    Returns:
        {"added": [(name, prop_count)], "removed": [(name, prop_count)],
         "changed": [(name, old_count, new_count)]}
    """
    old_names = set(old.keys())
    new_names = set(new.keys())

    added = sorted(
        [(name, len(new[name].get("properties", []))) for name in new_names - old_names]
    )
    removed = sorted(
        [(name, len(old[name].get("properties", []))) for name in old_names - new_names]
    )
    changed = []
    for name in sorted(old_names & new_names):
        old_count = len(old[name].get("properties", []))
        new_count = len(new[name].get("properties", []))
        if old_count != new_count:
            changed.append((name, old_count, new_count))

    return {"added": added, "removed": removed, "changed": changed}


def main(dataset: str):
    ds = load_dataset_config(dataset)
    clean_ref = ds["clean_ref"]
    min_triples = ds.get("min_triple_count", 0)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Pull clean artifact
        print(f"Pulling clean artifact: {clean_ref}")
        ttl_path = pull_dataset(clean_ref, tmpdir / "clean")

        # Triple count check
        verify_result = verify_turtle(ttl_path)
        count = verify_result.triple_count
        if min_triples and count < min_triples:
            print(f"FAIL: {dataset} — {count:,} triples (min: {min_triples:,})")
            sys.exit(1)
        print(f"PASS: {dataset} — {count:,} triples (min: {min_triples:,})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validate_dataset.py <dataset>")
        sys.exit(1)
    main(sys.argv[1])
