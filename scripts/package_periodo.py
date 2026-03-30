"""Download PeriodO JSON-LD, convert to Turtle, push to OCI registry."""

import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URL = "http://n2t.net/ark:/99152/p0d.jsonld"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/periodo"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://perio.do",
    "org.opencontainers.image.description": "PeriodO: A Gazetteer of Period Definitions — RDF dataset (converted from JSON-LD)",
    "org.opencontainers.image.licenses": "CC0-1.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/dprr-tool",
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
        print("Converting JSON-LD to Turtle...")
        from rdflib import Graph

        g = Graph()
        g.parse(str(jsonld_path), format="json-ld")
        ttl_path = tmpdir / "periodo.ttl"
        g.serialize(str(ttl_path), format="turtle")
        print(f"Created {ttl_path} ({ttl_path.stat().st_size:,} bytes), {len(g)} triples")
        ref = f"{ARTIFACT_REF}:{version}"
        print(f"Pushing to {ref}...")
        cmd = ["oras", "push", ref, "periodo.ttl:application/x-turtle"]
        for key, val in ANNOTATIONS.items():
            cmd.extend(["--annotation", f"{key}={val}"])
        cmd.extend(["--annotation", f"org.opencontainers.image.version={version}"])
        subprocess.run(cmd, cwd=str(tmpdir), check=True)
        print(f"Done: {ref}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
