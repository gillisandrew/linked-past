"""Download DPRR data and push to OCI registry."""

import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URL = "https://github.com/gillisandrew/dprr-mcp/releases/latest/download/dprr-data.tar.gz"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/dprr"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://romanrepublic.ac.uk",
    "org.opencontainers.image.description": "Digital Prosopography of the Roman Republic (DPRR) RDF dataset",
    "org.opencontainers.image.licenses": "CC-BY-NC-4.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/dprr-tool",
    "org.opencontainers.image.vendor": "King's College London",
    "dev.linked-past.dataset": "dprr",
    "dev.linked-past.source-url": SOURCE_URL,
    "dev.linked-past.format": "text/turtle",
}


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
        cmd = ["oras", "push", ref, "dprr.ttl:application/x-turtle"]
        for key, val in ANNOTATIONS.items():
            cmd.extend(["--annotation", f"{key}={val}"])
        cmd.extend(["--annotation", f"org.opencontainers.image.version={version}"])
        subprocess.run(cmd, cwd=str(tmpdir), check=True)
        print(f"Done: {ref}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
