"""Ingest EDH: extract Turtle from local zip, push raw to OCI."""

import sys
import tempfile
import zipfile
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config

LOCAL_ZIP = Path(__file__).parent.parent / "edh_linked_data.zip"


def main():
    ds = load_dataset_config("edh")

    if not LOCAL_ZIP.exists():
        print(f"ERROR: {LOCAL_ZIP} not found. Place edh_linked_data.zip in the project root.")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Extracting {LOCAL_ZIP}...")
        with zipfile.ZipFile(LOCAL_ZIP) as zf:
            zf.extractall(tmpdir / "raw")

        ttl_files = sorted((tmpdir / "raw").glob("*.ttl"))
        print(f"Found {len(ttl_files)} Turtle files")

        out_path = tmpdir / "edh.ttl"
        with open(out_path, "w") as out:
            for i, ttl in enumerate(ttl_files):
                if i > 0:
                    out.write("\n")
                out.write(ttl.read_text())
        print(f"Created edh.ttl ({out_path.stat().st_size:,} bytes)")

        # Push raw
        annotations = {
            **build_annotations(ds, "edh"),
            "io.github.gillisandrew.linked-past.source-url": "https://edh.ub.uni-heidelberg.de/data/export",
        }
        ref = ds["raw_ref"]
        digest = push_dataset(ref, out_path, annotations=annotations)
        print(f"Pushed raw: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main()
