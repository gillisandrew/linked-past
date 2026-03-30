"""Download PeriodO JSON-LD, convert to Turtle, push to OCI registry."""
import subprocess, sys, tempfile, urllib.request
from pathlib import Path

SOURCE_URL = "http://n2t.net/ark:/99152/p0d.jsonld"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/periodo"

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
        subprocess.run(["oras", "push", ref, "periodo.ttl:application/x-turtle"], cwd=str(tmpdir), check=True)
        print(f"Done: {ref}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
