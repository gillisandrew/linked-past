"""Download Nomisma concept vocabulary and push to OCI registry."""
import subprocess, sys, tempfile, urllib.request
from pathlib import Path

SOURCE_URL = "http://nomisma.org/nomisma.org.ttl"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/nomisma"

def main(version="latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        ttl_path = tmpdir / "nomisma.ttl"
        urllib.request.urlretrieve(SOURCE_URL, str(ttl_path))
        print(f"Downloaded {ttl_path} ({ttl_path.stat().st_size:,} bytes)")
        ref = f"{ARTIFACT_REF}:{version}"
        subprocess.run(["oras", "push", ref, "nomisma.ttl:application/x-turtle"], cwd=str(tmpdir), check=True)
        print(f"Done: {ref}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
