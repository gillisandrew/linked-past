"""Ingest Nomisma: download RDF/XML, convert to Turtle via rapper, push raw to OCI.

Corrects two mangled DBpedia URIs (Turkish characters lost as U+FFFD upstream).
"""

import subprocess
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config

FETCH_URL = "https://nomisma.org/nomisma.org.rdf"

# Upstream Nomisma export has two DBpedia URIs with mangled Turkish characters.
# The original bytes (ı, ğ) were lost and replaced with U+FFFD / '?'.
# Correct URIs verified against DBpedia on 2026-04-05.
_IRI_CORRECTIONS = {
    b"http://dbpedia.org/resource/Ayd\xef\xbf\xbdnc\xef\xbf\xbdk,_Mersin": b"http://dbpedia.org/resource/Ayd%C4%B1nc%C4%B1k,_Mersin",
    b"http://dbpedia.org/resource/Da?pazar\xef\xbf\xbd": b"http://dbpedia.org/resource/Da%C4%9Fpazar%C4%B1",
}


def main():
    ds = load_dataset_config("nomisma")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Downloading {FETCH_URL}...")
        rdf_path = tmpdir / "nomisma.rdf"
        urllib.request.urlretrieve(FETCH_URL, str(rdf_path))
        print(f"Downloaded ({rdf_path.stat().st_size:,} bytes)")

        # Fix known mangled IRIs in the source RDF/XML before conversion
        raw_bytes = rdf_path.read_bytes()
        for bad, good in _IRI_CORRECTIONS.items():
            if bad in raw_bytes:
                raw_bytes = raw_bytes.replace(bad, good)
                print(f"Fixed IRI: {good.decode()}")
        rdf_path.write_bytes(raw_bytes)

        print("Converting RDF/XML to Turtle via rapper...")
        ttl_path = tmpdir / "nomisma.ttl"
        with open(ttl_path, "w") as ttl_out:
            subprocess.run(
                ["rapper", "-i", "rdfxml", "-o", "turtle", "-q", str(rdf_path)],
                stdout=ttl_out,
                stderr=subprocess.PIPE,
                check=False,  # rapper returns 1 for warnings
            )
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
