"""Ingest DPRR: download tar.gz from GitHub release, push raw Turtle to OCI."""

import tarfile
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config

FETCH_URL = "https://github.com/gillisandrew/dprr-mcp/releases/latest/download/dprr-data.tar.gz"


def main():
    ds = load_dataset_config("dprr")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Downloading {FETCH_URL}...")
        tmp_path, _ = urllib.request.urlretrieve(FETCH_URL)
        with tarfile.open(tmp_path, "r:gz") as tar:
            tar.extract("dprr.ttl", path=str(tmpdir), filter="data")
        Path(tmp_path).unlink()

        data_file = tmpdir / "dprr.ttl"
        print(f"Extracted dprr.ttl ({data_file.stat().st_size:,} bytes)")

        # Push raw
        annotations = {
            **build_annotations(ds, "dprr"),
            "io.github.gillisandrew.linked-past.source-url": FETCH_URL,
        }
        ref = ds["raw_ref"]
        digest = push_dataset(ref, data_file, annotations=annotations)
        print(f"Pushed raw: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main()
