"""Download DPRR data and push to OCI registry."""
import subprocess, sys, tarfile, tempfile, urllib.request
from pathlib import Path

SOURCE_URL = "https://github.com/gillisandrew/dprr-mcp/releases/latest/download/dprr-data.tar.gz"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/dprr"

def main(version="latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        tmp_path, _ = urllib.request.urlretrieve(SOURCE_URL)
        with tarfile.open(tmp_path, "r:gz") as tar:
            tar.extract("dprr.ttl", path=str(tmpdir), filter="data")
        Path(tmp_path).unlink()
        ref = f"{ARTIFACT_REF}:{version}"
        print(f"Pushing to {ref}...")
        subprocess.run(["oras", "push", ref, "dprr.ttl:application/x-turtle"], cwd=str(tmpdir), check=True)
        print(f"Done: {ref}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
