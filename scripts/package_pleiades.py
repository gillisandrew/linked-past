"""Download Pleiades RDF dump and push to OCI registry."""

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
    "org.opencontainers.image.description": "Pleiades: A Gazetteer of Past Places — RDF dataset",
    "org.opencontainers.image.licenses": "CC-BY-3.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/dprr-tool",
    "org.opencontainers.image.vendor": "Institute for the Study of the Ancient World (NYU)",
    "dev.linked-past.dataset": "pleiades",
    "dev.linked-past.source-url": SOURCE_URL,
    "dev.linked-past.format": "text/turtle",
    "dev.linked-past.citation": "Bagnall, R. et al. (eds.), Pleiades: A Gazetteer of Past Places. DOI: 10.5281/zenodo.1193921",
}


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
        print(f"Pushing to {ref}...")
        cmd = ["oras", "push", ref, "pleiades.ttl:application/x-turtle"]
        for key, val in ANNOTATIONS.items():
            cmd.extend(["--annotation", f"{key}={val}"])
        cmd.extend(["--annotation", f"org.opencontainers.image.version={version}"])
        subprocess.run(cmd, cwd=str(tmpdir), check=True)
        print(f"Done: {ref}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "latest")
