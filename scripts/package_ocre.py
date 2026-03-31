"""Download OCRE RDF, convert to Turtle, generate VoID, and push to OCI registry."""

import sys
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset, verify_turtle
from linked_past_store.void import generate_void

SOURCE_URL = "https://numismatics.org/ocre/nomisma.rdf"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/ocre"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://numismatics.org/ocre",
    "org.opencontainers.image.description": "Online Coins of the Roman Empire — RIC coin type corpus",
    "org.opencontainers.image.licenses": "ODbL-1.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/linked-past",
    "org.opencontainers.image.vendor": "American Numismatic Society",
    "dev.linked-past.dataset": "ocre",
    "dev.linked-past.source-url": SOURCE_URL,
    "dev.linked-past.format": "text/turtle",
    "dev.linked-past.citation": "ANS, OCRE. Based on Mattingly et al., Roman Imperial Coinage (RIC)",
}


def main(version="latest"):
    from rdflib import Graph

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        rdf_path = tmpdir / "ocre.rdf"
        urllib.request.urlretrieve(SOURCE_URL, str(rdf_path))
        print(f"Downloaded {rdf_path} ({rdf_path.stat().st_size:,} bytes)")

        print("Converting RDF/XML to Turtle...")
        g = Graph()
        g.parse(str(rdf_path), format="xml")
        ttl_path = tmpdir / "ocre.ttl"
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
            dataset_id="ocre",
            title="Online Coins of the Roman Empire (OCRE)",
            license_uri="https://opendatacommons.org/licenses/odbl/1-0/",
            source_uri="https://numismatics.org/ocre",
            citation="ANS, OCRE. Based on Mattingly et al., Roman Imperial Coinage (RIC)",
            publisher="American Numismatic Society",
            output_path=tmpdir / "void.ttl",
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
            void_path=tmpdir / "void.ttl",
        )
        print(f"Done: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
