"""Extract EDH Turtle files from local zip, generate VoID, and push to OCI registry."""

import sys
import tempfile
import zipfile
from pathlib import Path

from linked_past_store import push_dataset, verify_turtle
from linked_past_store.void import generate_void

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
        with open(out_path, "w") as out:
            for i, ttl in enumerate(ttl_files):
                print(f"  Appending {ttl.name} ({ttl.stat().st_size:,} bytes)")
                content = ttl.read_text()
                if i > 0:
                    out.write("\n")
                out.write(content)

        print(f"Created {out_path} ({out_path.stat().st_size:,} bytes)")

        # Verify
        result = verify_turtle(out_path)
        if not result.ok:
            print(f"Verification failed: {result.errors[0]}")
            sys.exit(1)
        print(f"Verified: {result.triple_count:,} triples")

        # Generate VoID
        void = generate_void(
            data_path=out_path,
            dataset_id="edh",
            title="Epigraphic Database Heidelberg (EDH)",
            license_uri="https://creativecommons.org/licenses/by-sa/4.0/",
            source_uri="https://edh.ub.uni-heidelberg.de/",
            citation="Epigraphic Database Heidelberg, CC BY-SA 4.0",
            publisher="Heidelberg Academy of Sciences",
            output_path=tmpdir / "_void.ttl",
        )
        print(f"Generated VoID: {void.triples:,} triples, {void.classes} classes")

        # Push
        annotations = {
            **ANNOTATIONS,
            "org.opencontainers.image.version": version,
            "dev.linked-past.triples": str(result.triple_count),
        }
        ref = f"{ARTIFACT_REF}:{version}"
        digest = push_dataset(
            ref,
            out_path,
            annotations=annotations,
            void_path=tmpdir / "_void.ttl",
        )
        print(f"Done: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2021-12-16")
