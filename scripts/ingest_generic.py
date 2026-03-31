"""Generic dataset ingest: download from fetch_url, convert to Turtle, push to raw OCI."""

import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config


def main(dataset: str):
    ds = load_dataset_config(dataset)

    fetch_url = ds.get("fetch_url")
    source_format = ds.get("source_format")
    if not fetch_url or not source_format:
        print(f"ERROR: {dataset} requires fetch_url and source_format for generic ingest")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Download
        print(f"Downloading {fetch_url}...")
        raw_path = tmpdir / f"{dataset}_raw"
        urllib.request.urlretrieve(fetch_url, str(raw_path))
        print(f"Downloaded ({raw_path.stat().st_size:,} bytes)")

        # Convert to Turtle
        ttl_path = tmpdir / f"{dataset}.ttl"
        if source_format == "rdf-xml":
            print("Converting RDF/XML to Turtle via rapper...")
            with open(ttl_path, "w") as ttl_out:
                subprocess.run(
                    ["rapper", "-i", "rdfxml", "-o", "turtle", str(raw_path)],
                    stdout=ttl_out,
                    stderr=subprocess.PIPE,
                    check=True,
                )
        elif source_format == "json-ld":
            print("Converting JSON-LD to Turtle via rdflib...")
            from rdflib import Graph

            g = Graph()
            g.parse(str(raw_path), format="json-ld")
            g.serialize(str(ttl_path), format="turtle")
        elif source_format == "turtle":
            import shutil

            shutil.copy2(raw_path, ttl_path)
        else:
            print(f"ERROR: Unknown source_format {source_format!r}")
            sys.exit(1)

        print(f"Created {ttl_path.name} ({ttl_path.stat().st_size:,} bytes)")

        # Push raw
        annotations = {
            **build_annotations(ds, dataset),
            "io.github.gillisandrew.linked-past.source-url": fetch_url,
        }
        ref = ds["raw_ref"]
        digest = push_dataset(ref, ttl_path, annotations=annotations)
        print(f"Pushed raw: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ingest_generic.py <dataset>")
        sys.exit(1)
    main(sys.argv[1])
