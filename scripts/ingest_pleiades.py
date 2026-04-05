"""Ingest Pleiades: concatenate Turtle files from a local checkout, push raw to OCI.

Fixes percent-encoded fragment identifiers (%23 → #) in the source Turtle.

Primary ingest is via GitHub Actions (ingest-pleiades.yml) which checks out
isawnyu/pleiades.datasets directly. This script supports local runs when a
checkout of that repo is available.

Usage:
    python -m scripts.ingest_pleiades /path/to/pleiades.datasets/data/rdf
"""

import sys
import tempfile
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config

SOURCE_REPO = "https://github.com/isawnyu/pleiades.datasets"

# All vocabulary URIs in the Pleiades dump are missing the place-types/ segment.
# e.g., /vocabularies/abbey should be /vocabularies/place-types/abbey
VOCAB_FIXED = "pleiades.stoa.org/vocabularies/place-types/"
VOCAB_BROKEN = "pleiades.stoa.org/vocabularies/"


def main(rdf_dir: str):
    rdf_path = Path(rdf_dir)
    if not rdf_path.is_dir():
        print(f"ERROR: {rdf_path} is not a directory")
        print("Clone https://github.com/isawnyu/pleiades.datasets and pass the data/rdf/ path.")
        sys.exit(1)

    ds = load_dataset_config("pleiades")

    ttl_files = sorted(rdf_path.glob("*.ttl"))
    if not ttl_files:
        print(f"ERROR: No .ttl files found in {rdf_path}")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        output = tmpdir / "pleiades.ttl"

        print(f"Concatenating {len(ttl_files)} Turtle files from {rdf_path}...")
        fix_count = 0
        vocab_fix_count = 0
        with open(output, "w") as out:
            for ttl in ttl_files:
                text = ttl.read_text()
                # Fix percent-encoded fragment identifiers (%23 → #).
                # Pleiades source data encodes '#' as '%23' in ~100K IRIs,
                # making them path components instead of fragment identifiers.
                count = text.count("%23")
                if count:
                    text = text.replace("%23", "#")
                    fix_count += count

                # Fix vocabulary URIs missing place-types/ segment.
                # All ~159K vocabulary references use /vocabularies/abbey
                # instead of the correct /vocabularies/place-types/abbey.
                # Guard against double-replacement by protecting already-correct URIs.
                vocab_count = text.count(VOCAB_BROKEN) - text.count(VOCAB_FIXED)
                if vocab_count > 0:
                    text = text.replace(VOCAB_FIXED, "\x00PLACEHOLDER\x00")
                    text = text.replace(VOCAB_BROKEN, VOCAB_FIXED)
                    text = text.replace("\x00PLACEHOLDER\x00", VOCAB_FIXED)
                    vocab_fix_count += vocab_count
                out.write(f"# Source: {ttl.name}\n")
                out.write(text)
                out.write("\n\n")

        if fix_count:
            print(f"Fixed {fix_count:,} percent-encoded fragment identifiers (%23 → #)")
        if vocab_fix_count:
            print(f"Fixed {vocab_fix_count:,} vocabulary URIs (added place-types/ segment)")
        print(f"Created pleiades.ttl ({output.stat().st_size:,} bytes)")

        # Push raw
        annotations = {
            **build_annotations(ds, "pleiades"),
            "io.github.gillisandrew.linked-past.source-url": SOURCE_REPO,
        }
        ref = ds["raw_ref"]
        digest = push_dataset(ref, output, annotations=annotations)
        print(f"Pushed raw: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ingest_pleiades.py <path-to-pleiades-rdf-dir>")
        print("  e.g.: python -m scripts.ingest_pleiades ~/pleiades.datasets/data/rdf")
        sys.exit(1)
    main(sys.argv[1])
