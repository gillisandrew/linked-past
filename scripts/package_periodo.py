"""Download PeriodO JSON-LD, convert to Turtle, generate VoID, and push to OCI registry."""

import sys
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset, verify_turtle
from linked_past_store.void import generate_void

SOURCE_URL = "http://n2t.net/ark:/99152/p0d.jsonld"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/periodo"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://perio.do",
    "org.opencontainers.image.description": (
        "PeriodO: A Gazetteer of Period Definitions (converted from JSON-LD)"
    ),
    "org.opencontainers.image.licenses": "CC0-1.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/linked-past",
    "org.opencontainers.image.vendor": "PeriodO project (UNC Chapel Hill / UT Austin)",
    "dev.linked-past.dataset": "periodo",
    "dev.linked-past.source-url": SOURCE_URL,
    "dev.linked-past.format": "text/turtle",
    "dev.linked-past.citation": "Golden, P. & Shaw, R. (2016). PeerJ Computer Science 2:e44",
}


def main(version="latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        jsonld_path = tmpdir / "periodo.jsonld"
        urllib.request.urlretrieve(SOURCE_URL, str(jsonld_path))
        print(f"Downloaded ({jsonld_path.stat().st_size:,} bytes)")

        print("Converting JSON-LD to Turtle...")
        from rdflib import Graph

        g = Graph()
        g.parse(str(jsonld_path), format="json-ld")
        ttl_path = tmpdir / "periodo.ttl"
        g.serialize(str(ttl_path), format="turtle")
        print(f"Created {ttl_path} ({ttl_path.stat().st_size:,} bytes), {len(g)} triples")

        # Verify
        result = verify_turtle(ttl_path)
        if not result.ok:
            print(f"Verification failed: {result.errors[0]}")
            sys.exit(1)
        print(f"Verified: {result.triple_count:,} triples")

        # Generate VoID
        void = generate_void(
            data_path=ttl_path,
            dataset_id="periodo",
            title="PeriodO: A Gazetteer of Period Definitions",
            license_uri="https://creativecommons.org/publicdomain/zero/1.0/",
            source_uri="https://perio.do/",
            citation="Golden, P. & Shaw, R. (2016). PeerJ Computer Science 2:e44",
            publisher="PeriodO project (UNC Chapel Hill / UT Austin)",
            output_path=tmpdir / "_void.ttl",
        )
        print(f"Generated VoID: {void.triples:,} triples, {void.classes} classes")

        # Push
        annotations = {
            **ANNOTATIONS,
            "org.opencontainers.image.version": version,
            "dev.linked-past.triples": str(result.triple_count),
        }
        ref = f"{ARTIFACT_REF}:{version}"
        digest = push_dataset(
            ref,
            ttl_path,
            annotations=annotations,
            void_path=tmpdir / "_void.ttl",
        )
        print(f"Done: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
