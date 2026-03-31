"""Download OCRE RDF, convert to Turtle via rapper, generate VoID, and push to OCI registry."""

import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset, verify_turtle
from linked_past_store.ontology import extract_schema, generate_schemas_yaml
from linked_past_store.void import generate_void

SOURCE_URL = "https://numismatics.org/ocre/nomisma.rdf"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/ocre"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://numismatics.org/ocre",
    "org.opencontainers.image.description": "Online Coins of the Roman Empire — RIC coin type corpus",
    "org.opencontainers.image.licenses": "ODbL-1.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/linked-past",
    "org.opencontainers.image.vendor": "American Numismatic Society",
    "io.github.gillisandrew.linked-past.dataset": "ocre",
    "io.github.gillisandrew.linked-past.source-url": SOURCE_URL,
    "io.github.gillisandrew.linked-past.format": "text/turtle",
    "io.github.gillisandrew.linked-past.citation": "ANS, OCRE. Based on Mattingly et al., Roman Imperial Coinage (RIC)",
}


def main(version="latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        rdf_path = tmpdir / "ocre.rdf"
        urllib.request.urlretrieve(SOURCE_URL, str(rdf_path))
        print(f"Downloaded {rdf_path} ({rdf_path.stat().st_size:,} bytes)")

        print("Converting RDF/XML to Turtle via rapper...")
        ttl_path = tmpdir / "ocre.ttl"
        subprocess.run(
            ["rapper", "-i", "rdfxml", "-o", "turtle", str(rdf_path)],
            stdout=open(ttl_path, "w"),
            stderr=subprocess.PIPE,
            check=True,
        )
        print(f"Created {ttl_path} ({ttl_path.stat().st_size:,} bytes)")

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
            output_path=tmpdir / "_void.ttl",
        )
        print(f"Generated VoID: {void.triples:,} triples, {void.classes} classes")

        # Extract schema
        schema = extract_schema(data_path=ttl_path)
        generate_schemas_yaml(schema, tmpdir / "_schema.yaml")
        print(f"Extracted schema: {len(schema.classes)} classes")

        # Push
        annotations = {
            **ANNOTATIONS,
            "org.opencontainers.image.version": version,
            "io.github.gillisandrew.linked-past.triples": str(result.triple_count),
        }
        ref = f"{ARTIFACT_REF}:{version}"
        digest = push_dataset(
            ref,
            [ttl_path, tmpdir / "_void.ttl", tmpdir / "_schema.yaml"],
            annotations=annotations,
        )
        print(f"Done: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
