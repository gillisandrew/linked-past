"""Download Pleiades RDF dump, sanitize for Oxigraph, and push to OCI registry.

The upstream Pleiades Turtle has language tags that violate BCP 47
(subtags longer than 8 characters, e.g., @etruscan-in-latin-characters).
We fix these by truncating/replacing invalid language tags, then verify
with pyoxigraph.
"""

import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URL = "https://atlantides.org/downloads/pleiades/rdf/pleiades-latest.tar.gz"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/pleiades"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://pleiades.stoa.org",
    "org.opencontainers.image.description": "Pleiades: A Gazetteer of Past Places — RDF dataset (sanitized for Oxigraph)",
    "org.opencontainers.image.licenses": "CC-BY-3.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/linked-past",
    "org.opencontainers.image.vendor": "Institute for the Study of the Ancient World (NYU)",
    "dev.linked-past.dataset": "pleiades",
    "dev.linked-past.source-url": SOURCE_URL,
    "dev.linked-past.format": "text/turtle",
    "dev.linked-past.citation": "Bagnall, R. et al. (eds.), Pleiades: A Gazetteer of Past Places. DOI: 10.5281/zenodo.1193921",
}

# BCP 47: subtags must be max 8 characters
_LANG_TAG = re.compile(r'"([^"]*)"@([a-zA-Z][a-zA-Z0-9-]*)')


def _fix_lang_tag(match: re.Match) -> str:
    """Fix language tags with subtags exceeding 8 characters."""
    text = match.group(1)
    tag = match.group(2)
    # Check each subtag
    parts = tag.split("-")
    fixed_parts = []
    for part in parts:
        if len(part) > 8:
            # Truncate to 8 chars (BCP 47 max subtag length)
            fixed_parts.append(part[:8])
        else:
            fixed_parts.append(part)
    fixed_tag = "-".join(fixed_parts)
    return f'"{text}"@{fixed_tag}'


_BARE_DOI = re.compile(r'<(doi\.org/)')


def _sanitize_turtle(text: str) -> tuple[str, int]:
    """Fix known issues in Pleiades Turtle."""
    fixes = 0
    text, n = _LANG_TAG.subn(_fix_lang_tag, text)
    fixes += n
    # Fix bare DOIs missing scheme: <doi.org/...> → <https://doi.org/...>
    text, n = _BARE_DOI.subn(r'<https://\1', text)
    fixes += n
    return text, fixes


def main(version="latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        tmp_path, _ = urllib.request.urlretrieve(SOURCE_URL)

        # Concatenate all .ttl files
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

        # Fix language tags
        print("Sanitizing (fixing BCP 47 language tags)...")
        text = raw.read_text()
        fixed_text, fix_count = _sanitize_turtle(text)
        print(f"Applied fixes to {fix_count} language-tagged literals")

        output = tmpdir / "pleiades.ttl"
        output.write_text(fixed_text)

        # Verify with pyoxigraph
        print("Verifying with pyoxigraph...")
        from pyoxigraph import RdfFormat, Store
        store = Store()
        store.bulk_load(path=str(output), format=RdfFormat.TURTLE)
        print(f"Verified: {len(store):,} triples")
        del store

        ref = f"{ARTIFACT_REF}:{version}"
        print(f"Pushing to {ref}...")
        cmd = ["oras", "push", ref, "pleiades.ttl:application/x-turtle"]
        for key, val in ANNOTATIONS.items():
            cmd.extend(["--annotation", f"{key}={val}"])
        cmd.extend(["--annotation", f"org.opencontainers.image.version={version}"])
        subprocess.run(cmd, cwd=str(tmpdir), check=True)
        print(f"Done: {ref}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
