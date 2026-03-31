"""Ingest PeriodO: download JSON-LD, convert to Turtle via rdflib, push raw to OCI."""

import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config

FETCH_URL = "http://n2t.net/ark:/99152/p0d.jsonld"


def main():
    ds = load_dataset_config("periodo")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Downloading {FETCH_URL}...")
        jsonld_path = tmpdir / "periodo.jsonld"
        urllib.request.urlretrieve(FETCH_URL, str(jsonld_path))
        print(f"Downloaded ({jsonld_path.stat().st_size:,} bytes)")

        print("Converting JSON-LD to Turtle...")
        from rdflib import Graph

        g = Graph()
        g.parse(str(jsonld_path), format="json-ld")
        ttl_path = tmpdir / "periodo.ttl"
        g.serialize(str(ttl_path), format="turtle")
        print(f"Created periodo.ttl ({ttl_path.stat().st_size:,} bytes), {len(g)} triples")

        # Push raw
        annotations = {
            **build_annotations(ds, "periodo"),
            "io.github.gillisandrew.linked-past.source-url": FETCH_URL,
        }
        ref = ds["raw_ref"]
        digest = push_dataset(ref, ttl_path, annotations=annotations)
        print(f"Pushed raw: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main()
