"""Download Pleiades RDF dump, sanitize for Oxigraph, generate VoID, and push to OCI registry."""

import re
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset, verify_turtle
from linked_past_store.ontology import extract_schema, generate_schemas_yaml
from linked_past_store.void import generate_void

SOURCE_URL = "https://atlantides.org/downloads/pleiades/rdf/pleiades-latest.tar.gz"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/pleiades"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://pleiades.stoa.org",
    "org.opencontainers.image.description": (
        "Pleiades: A Gazetteer of Past Places (sanitized for Oxigraph)"
    ),
    "org.opencontainers.image.licenses": "CC-BY-3.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/linked-past",
    "org.opencontainers.image.vendor": "Institute for the Study of the Ancient World (NYU)",
    "io.github.gillisandrew.linked-past.dataset": "pleiades",
    "io.github.gillisandrew.linked-past.source-url": SOURCE_URL,
    "io.github.gillisandrew.linked-past.format": "text/turtle",
    "io.github.gillisandrew.linked-past.citation": (
        "Bagnall, R. et al. (eds.), Pleiades. DOI: 10.5281/zenodo.1193921"
    ),
}

# BCP 47: subtags must be max 8 characters
_LANG_TAG = re.compile(r'"([^"]*)"@([a-zA-Z][a-zA-Z0-9-]*)')
_BARE_DOI = re.compile(r'<(doi\.org/)')


def _fix_lang_tag(match: re.Match) -> str:
    text = match.group(1)
    tag = match.group(2)
    parts = tag.split("-")
    fixed_parts = [part[:8] if len(part) > 8 else part for part in parts]
    return f'"{text}"@{"-".join(fixed_parts)}'


def _sanitize_pleiades(text: str) -> tuple[str, int]:
    fixes = 0
    text, n = _LANG_TAG.subn(_fix_lang_tag, text)
    fixes += n
    text, n = _BARE_DOI.subn(r'<https://\1', text)
    fixes += n
    return text, fixes


def main(version="latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        tmp_path, _ = urllib.request.urlretrieve(SOURCE_URL)

        print("Extracting and concatenating Turtle files...")
        raw = tmpdir / "pleiades_raw.ttl"
        with tarfile.open(tmp_path, "r:gz") as tar, open(raw, "w") as out:
            for member in sorted(tar.getnames()):
                if member.endswith(".ttl"):
                    f = tar.extractfile(member)
                    if f:
                        out.write(f"# Source: {member}\n")
                        out.write(f.read().decode("utf-8"))
                        out.write("\n\n")
        Path(tmp_path).unlink()
        print(f"Raw: {raw.stat().st_size:,} bytes")

        # Fix Pleiades-specific issues
        print("Sanitizing (fixing BCP 47 language tags)...")
        text = raw.read_text()
        fixed_text, fix_count = _sanitize_pleiades(text)
        print(f"Applied fixes to {fix_count} literals")

        output = tmpdir / "pleiades.ttl"
        output.write_text(fixed_text)

        # Verify
        result = verify_turtle(output)
        if not result.ok:
            print(f"Verification failed: {result.errors[0]}")
            sys.exit(1)
        print(f"Verified: {result.triple_count:,} triples")

        # Generate VoID
        void = generate_void(
            data_path=output,
            dataset_id="pleiades",
            title="Pleiades: A Gazetteer of Past Places",
            license_uri="https://creativecommons.org/licenses/by/3.0/",
            source_uri="https://pleiades.stoa.org/",
            citation="Bagnall, R. et al. (eds.), Pleiades. DOI: 10.5281/zenodo.1193921",
            publisher="Institute for the Study of the Ancient World (NYU)",
            output_path=tmpdir / "_void.ttl",
        )
        print(f"Generated VoID: {void.triples:,} triples, {void.classes} classes")

        # Extract schema
        schema = extract_schema(data_path=output)
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
            [output, tmpdir / "_void.ttl", tmpdir / "_schema.yaml"],
            annotations=annotations,
        )
        print(f"Done: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
