"""Download Pleiades RDF dump and push to OCI registry."""
import subprocess, sys, tarfile, tempfile, urllib.request
from pathlib import Path

SOURCE_URL = "https://atlantides.org/downloads/pleiades/rdf/pleiades-latest.tar.gz"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/pleiades"

def main(version="latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        tmp_path, _ = urllib.request.urlretrieve(SOURCE_URL)
        print("Extracting and concatenating Turtle files...")
        output = tmpdir / "pleiades.ttl"
        with tarfile.open(tmp_path, "r:gz") as tar, open(output, "w") as out:
            for member in sorted(tar.getnames()):
                if member.endswith(".ttl"):
                    f = tar.extractfile(member)
                    if f:
                        out.write(f"# Source: {member}\n")
                        out.write(f.read().decode("utf-8"))
                        out.write("\n\n")
        Path(tmp_path).unlink()
        print(f"Created {output} ({output.stat().st_size:,} bytes)")
        ref = f"{ARTIFACT_REF}:{version}"
        subprocess.run(["oras", "push", ref, "pleiades.ttl:application/x-turtle"], cwd=str(tmpdir), check=True)
        print(f"Done: {ref}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
