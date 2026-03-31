"""Ingest Pleiades: download tar.gz, concatenate Turtle files, push raw to OCI."""

import tarfile
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config

FETCH_URL = "https://atlantides.org/downloads/pleiades/rdf/pleiades-latest.tar.gz"


def main():
    ds = load_dataset_config("pleiades")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Downloading {FETCH_URL}...")
        tmp_path, _ = urllib.request.urlretrieve(FETCH_URL)

        print("Extracting and concatenating Turtle files...")
        output = tmpdir / "pleiades.ttl"
        with tarfile.open(tmp_path, "r:gz") as tar, open(output, "w") as out:
            for member in sorted(tar.getnames()):
                if member.endswith(".ttl"):
                    f = tar.extractfile(member)
                    if f:
                        out.write(f"# Source: {member}\n")
                        out.write(f.read().decode("utf-8"))
                        out.write("\n\n")
        Path(tmp_path).unlink()
        print(f"Created pleiades.ttl ({output.stat().st_size:,} bytes)")

        # Push raw (unsanitized — clean step handles BCP 47 fixes)
        annotations = {
            **build_annotations(ds, "pleiades"),
            "io.github.gillisandrew.linked-past.source-url": FETCH_URL,
        }
        ref = ds["raw_ref"]
        digest = push_dataset(ref, output, annotations=annotations)
        print(f"Pushed raw: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main()
