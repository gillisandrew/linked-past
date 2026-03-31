"""Extract EDH Turtle files from local zip, concatenate, and push to OCI registry."""

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

LOCAL_ZIP = Path(__file__).parent.parent / "edh_linked_data.zip"
ARTIFACT_REF = "ghcr.io/gillisandrew/linked-past/edh"

ANNOTATIONS = {
    "org.opencontainers.image.source": "https://edh.ub.uni-heidelberg.de",
    "org.opencontainers.image.description": "Epigraphic Database Heidelberg — 81K+ Latin inscriptions",
    "org.opencontainers.image.licenses": "CC-BY-SA-4.0",
    "org.opencontainers.image.url": "https://github.com/gillisandrew/linked-past",
    "org.opencontainers.image.vendor": "Heidelberg Academy of Sciences",
    "dev.linked-past.dataset": "edh",
    "dev.linked-past.source-url": "https://edh.ub.uni-heidelberg.de/data/export",
    "dev.linked-past.format": "text/turtle",
    "dev.linked-past.citation": "Epigraphic Database Heidelberg, CC BY-SA 4.0",
}


def main(version="2021-12-16"):
    if not LOCAL_ZIP.exists():
        print(f"ERROR: {LOCAL_ZIP} not found. Place edh_linked_data.zip in the project root.")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        print(f"Extracting {LOCAL_ZIP}...")
        with zipfile.ZipFile(LOCAL_ZIP) as zf:
            zf.extractall(tmpdir / "raw")

        raw_dir = tmpdir / "raw"
        ttl_files = sorted(raw_dir.glob("*.ttl"))
        print(f"Found {len(ttl_files)} Turtle files")

        out_path = tmpdir / "edh.ttl"
        total_size = 0
        with open(out_path, "w") as out:
            for i, ttl in enumerate(ttl_files):
                print(f"  Appending {ttl.name} ({ttl.stat().st_size:,} bytes)")
                content = ttl.read_text()
                if i > 0:
                    out.write("\n")
                out.write(content)
                total_size += ttl.stat().st_size

        print(f"Created {out_path} ({out_path.stat().st_size:,} bytes)")

        ref = f"{ARTIFACT_REF}:{version}"
        print(f"Pushing to {ref}...")
        cmd = ["oras", "push", ref, "edh.ttl:application/x-turtle"]
        for key, val in ANNOTATIONS.items():
            cmd.extend(["--annotation", f"{key}={val}"])
        cmd.extend(["--annotation", f"org.opencontainers.image.version={version}"])
        subprocess.run(cmd, cwd=str(tmpdir), check=True)
        print(f"Done: {ref}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2021-12-16")
