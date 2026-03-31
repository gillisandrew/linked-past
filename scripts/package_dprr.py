"""Download DPRR data, generate VoID, and push to OCI registry."""

import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset, verify_turtle
from linked_past_store.ontology import extract_schema, generate_schemas_yaml
from linked_past_store.void import generate_void

SOURCE_URL = "https://github.com/gillisandrew/dprr-mcp/releases/latest/download/dprr-data.tar.gz"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/dprr"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://romanrepublic.ac.uk",
    "org.opencontainers.image.description": "Digital Prosopography of the Roman Republic (DPRR) RDF dataset",
    "org.opencontainers.image.licenses": "CC-BY-NC-4.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/linked-past",
    "org.opencontainers.image.vendor": "King's College London",
    "io.github.gillisandrew.linked-past.dataset": "dprr",
    "io.github.gillisandrew.linked-past.source-url": SOURCE_URL,
    "io.github.gillisandrew.linked-past.format": "text/turtle",
}


def main(version="latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        tmp_path, _ = urllib.request.urlretrieve(SOURCE_URL)
        with tarfile.open(tmp_path, "r:gz") as tar:
            tar.extract("dprr.ttl", path=str(tmpdir), filter="data")
        Path(tmp_path).unlink()

        data_file = tmpdir / "dprr.ttl"

        # Verify
        result = verify_turtle(data_file)
        if not result.ok:
            print(f"Verification failed: {result.errors[0]}")
            sys.exit(1)
        print(f"Verified: {result.triple_count:,} triples")

        # Generate VoID
        void = generate_void(
            data_path=data_file,
            dataset_id="dprr",
            title="Digital Prosopography of the Roman Republic (DPRR)",
            license_uri="https://creativecommons.org/licenses/by-nc/4.0/",
            source_uri="https://romanrepublic.ac.uk/",
            citation="Mouritsen et al., DPRR, King's Digital Lab, 2017. https://romanrepublic.ac.uk/",
            publisher="King's College London",
            output_path=tmpdir / "_void.ttl",
        )
        print(f"Generated VoID: {void.triples:,} triples, {void.classes} classes")

        # Extract schema
        schema = extract_schema(data_path=data_file)
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
            [data_file, tmpdir / "_void.ttl", tmpdir / "_schema.yaml"],
            annotations=annotations,
        )
        print(f"Done: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
