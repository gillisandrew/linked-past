"""Download Nomisma concept vocabulary and push to OCI registry."""

import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URL = "http://nomisma.org/nomisma.org.ttl"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/nomisma"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://nomisma.org",
    "org.opencontainers.image.description": "Nomisma.org numismatic concept vocabulary — RDF dataset (concept definitions only)",
    "org.opencontainers.image.licenses": "CC-BY-4.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/dprr-tool",
    "org.opencontainers.image.vendor": "Nomisma.org / American Numismatic Society",
    "dev.linked-past.dataset": "nomisma",
    "dev.linked-past.source-url": SOURCE_URL,
    "dev.linked-past.format": "text/turtle",
    "dev.linked-past.citation": "Gruber, E. & Meadows, A. (2021). ISAW Papers 20.6",
}


def main(version="latest"):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"Downloading {SOURCE_URL}...")
        ttl_path = tmpdir / "nomisma.ttl"
        urllib.request.urlretrieve(SOURCE_URL, str(ttl_path))
        print(f"Downloaded {ttl_path} ({ttl_path.stat().st_size:,} bytes)")
        ref = f"{ARTIFACT_REF}:{version}"
        print(f"Pushing to {ref}...")
        cmd = ["oras", "push", ref, "nomisma.ttl:application/x-turtle"]
        for key, val in ANNOTATIONS.items():
            cmd.extend(["--annotation", f"{key}={val}"])
        cmd.extend(["--annotation", f"org.opencontainers.image.version={version}"])
        subprocess.run(cmd, cwd=str(tmpdir), check=True)
        print(f"Done: {ref}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
