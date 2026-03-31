"""Download Nomisma RDF/XML, convert to Turtle via rapper, sanitize, and push to OCI registry.

The upstream Nomisma RDF/XML is cleaner than the Turtle export. We convert
via rapper (fast, C-based), then fix any remaining issues (bad Unicode IRIs).
"""

import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset, verify_turtle
from linked_past_store.ontology import extract_schema, generate_schemas_yaml
from linked_past_store.void import generate_void

SOURCE_URL = "https://nomisma.org/nomisma.org.rdf"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/datasets/nomisma"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://github.com/gillisandrew/linked-past",
    "org.opencontainers.image.description": (
        "Nomisma.org numismatic concept vocabulary (sanitized for Oxigraph)"
    ),
    "org.opencontainers.image.licenses": "CC-BY-4.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/linked-past",
    "org.opencontainers.image.vendor": "Nomisma.org / American Numismatic Society",
    "io.github.gillisandrew.linked-past.dataset": "nomisma",
    "io.github.gillisandrew.linked-past.source-url": SOURCE_URL,
    "io.github.gillisandrew.linked-past.format": "text/turtle",
    "io.github.gillisandrew.linked-past.citation": "Gruber, E. & Meadows, A. (2021). ISAW Papers 20.6",
}

# Unicode replacement character — appears in a few IRIs after rapper conversion
_BAD_UNICODE = re.compile(r".*\ufffd.*\n?")


def main(version="latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        rdf_path = tmpdir / "nomisma.rdf"
        urllib.request.urlretrieve(SOURCE_URL, str(rdf_path))
        print(f"Downloaded {rdf_path} ({rdf_path.stat().st_size:,} bytes)")

        print("Converting RDF/XML to Turtle via rapper...")
        raw_ttl = tmpdir / "nomisma_raw.ttl"
        subprocess.run(
            ["rapper", "-i", "rdfxml", "-o", "turtle", "-q", str(rdf_path)],
            stdout=open(raw_ttl, "w"),
            stderr=subprocess.PIPE,
            check=False,  # rapper returns 1 for warnings (bad xsd:double literals)
        )
        print(f"Created {raw_ttl} ({raw_ttl.stat().st_size:,} bytes)")

        # Remove lines with invalid Unicode (replacement character in IRIs)
        text = raw_ttl.read_text(errors="replace")
        clean_text, fix_count = _BAD_UNICODE.subn("", text)
        clean_path = tmpdir / "nomisma.ttl"
        clean_path.write_text(clean_text)
        if fix_count:
            print(f"Removed {fix_count} lines with bad Unicode")

        # Verify
        result = verify_turtle(clean_path)
        if not result.ok:
            print(f"Verification failed: {result.errors[0]}")
            sys.exit(1)
        print(f"Verified: {result.triple_count:,} triples")

        # Generate VoID
        void = generate_void(
            data_path=clean_path,
            dataset_id="nomisma",
            title="Nomisma.org Numismatic Concept Vocabulary",
            license_uri="https://creativecommons.org/licenses/by/4.0/",
            source_uri="https://nomisma.org/",
            citation="Gruber, E. & Meadows, A. (2021). ISAW Papers 20.6",
            publisher="Nomisma.org / American Numismatic Society",
            output_path=tmpdir / "_void.ttl",
        )
        print(f"Generated VoID: {void.triples:,} triples, {void.classes} classes")

        # Extract schema
        schema = extract_schema(data_path=clean_path)
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
            [clean_path, tmpdir / "_void.ttl", tmpdir / "_schema.yaml"],
            annotations=annotations,
        )
        print(f"Done: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
