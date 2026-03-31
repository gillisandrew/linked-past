"""Download CRRO RDF, convert to Turtle, and push to OCI registry."""

import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URL = "https://numismatics.org/crro/nomisma.rdf"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/crro"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://numismatics.org/crro",
    "org.opencontainers.image.description": "Coinage of the Roman Republic Online — RRC coin type corpus",
    "org.opencontainers.image.licenses": "ODbL-1.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/dprr-tool",
    "org.opencontainers.image.vendor": "American Numismatic Society",
    "dev.linked-past.dataset": "crro",
    "dev.linked-past.source-url": SOURCE_URL,
    "dev.linked-past.format": "text/turtle",
    "dev.linked-past.citation": "ANS, CRRO. Based on Crawford (1974) Roman Republican Coinage",
}


def main(version="latest"):
    from rdflib import Graph

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        rdf_path = tmpdir / "crro.rdf"
        urllib.request.urlretrieve(SOURCE_URL, str(rdf_path))
        print(f"Downloaded {rdf_path} ({rdf_path.stat().st_size:,} bytes)")

        print("Converting RDF/XML to Turtle...")
        g = Graph()
        g.parse(str(rdf_path), format="xml")
        ttl_path = tmpdir / "crro.ttl"
        g.serialize(str(ttl_path), format="turtle")
        print(f"Created {ttl_path} ({ttl_path.stat().st_size:,} bytes), {len(g)} triples")

        ref = f"{ARTIFACT_REF}:{version}"
        print(f"Pushing to {ref}...")
        cmd = ["oras", "push", ref, "crro.ttl:application/x-turtle"]
        for key, val in ANNOTATIONS.items():
            cmd.extend(["--annotation", f"{key}={val}"])
        cmd.extend(["--annotation", f"org.opencontainers.image.version={version}"])
        subprocess.run(cmd, cwd=str(tmpdir), check=True)
        print(f"Done: {ref}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
