"""Ingest Nomisma: download RDF/XML, convert to Turtle via rapper, push raw to OCI.

Removes lines with Unicode replacement characters (bad IRIs in upstream data).
"""

import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config

FETCH_URL = "https://nomisma.org/nomisma.org.rdf"
_BAD_UNICODE = re.compile(r".*\ufffd.*\n?")


def main():
    ds = load_dataset_config("nomisma")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Downloading {FETCH_URL}...")
        rdf_path = tmpdir / "nomisma.rdf"
        urllib.request.urlretrieve(FETCH_URL, str(rdf_path))
        print(f"Downloaded ({rdf_path.stat().st_size:,} bytes)")

        print("Converting RDF/XML to Turtle via rapper...")
        raw_ttl = tmpdir / "nomisma_raw.ttl"
        with open(raw_ttl, "w") as ttl_out:
            subprocess.run(
                ["rapper", "-i", "rdfxml", "-o", "turtle", "-q", str(rdf_path)],
                stdout=ttl_out,
                stderr=subprocess.PIPE,
                check=False,  # rapper returns 1 for warnings
            )

        # Remove lines with bad Unicode
        text = raw_ttl.read_text(errors="replace")
        clean_text, fix_count = _BAD_UNICODE.subn("", text)
        ttl_path = tmpdir / "nomisma.ttl"
        ttl_path.write_text(clean_text)
        if fix_count:
            print(f"Removed {fix_count} lines with bad Unicode")
        print(f"Created nomisma.ttl ({ttl_path.stat().st_size:,} bytes)")

        # Push raw
        annotations = {
            **build_annotations(ds, "nomisma"),
            "io.github.gillisandrew.linked-past.source-url": FETCH_URL,
        }
        ref = ds["raw_ref"]
        digest = push_dataset(ref, ttl_path, annotations=annotations)
        print(f"Pushed raw: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main()
