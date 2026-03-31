"""Clean a raw dataset: pull from raw OCI, sanitize, verify, generate metadata, push clean.

Also runs schema diff against the previous version (if available) before pushing,
since both schemas are in memory at that point.
"""

import sys
import tempfile
from pathlib import Path

import yaml
from linked_past_store import (
    ArtifactCache,
    pull_dataset,
    push_dataset,
    sanitize_turtle,
    verify_turtle,
)
from linked_past_store.ontology import extract_schema, generate_schemas_yaml
from linked_past_store.void import generate_void

from scripts.pipeline_config import build_annotations, load_dataset_config, render_citation
from scripts.validate_dataset import diff_schemas


def main(dataset: str, version: str = "latest"):
    ds = load_dataset_config(dataset)
    raw_ref = ds["raw_ref"]
    clean_ref = ds["clean_ref"]

    # Replace tag if version override provided
    if version != "latest":
        base = clean_ref.rsplit(":", 1)[0]
        clean_ref = f"{base}:{version}"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Pull raw artifact and record its digest
        print(f"Pulling raw artifact: {raw_ref}")
        try:
            raw_ttl = pull_dataset(raw_ref, tmpdir / "raw")
        except RuntimeError as e:
            print(f"ERROR: Could not pull raw artifact {raw_ref}: {e}")
            print("Run the ingest script first to push raw data to OCI.")
            sys.exit(1)
        cache = ArtifactCache()
        raw_digest = cache.digest_for(raw_ref) or "unknown"
        print(f"Raw digest: {raw_digest}")

        # Load previous schema for diff (before we overwrite the cache)
        old_schema = {}
        try:
            pull_dataset(clean_ref, tmpdir / "prev")
            prev_schema_path = tmpdir / "prev" / "_schema.yaml"
            if prev_schema_path.exists():
                with open(prev_schema_path) as f:
                    old_schema = yaml.safe_load(f).get("classes", {})
                print("Loaded previous schema for diff")
        except Exception:
            print("No previous clean artifact found (first publish)")

        # Sanitize
        print("Sanitizing...")
        clean_ttl = tmpdir / f"{dataset}.ttl"
        sanitize_result = sanitize_turtle(raw_ttl, clean_ttl)
        print(f"Sanitized: {sanitize_result.fixes_applied} fixes applied")

        # Verify
        verify_result = verify_turtle(clean_ttl)
        if not verify_result.ok:
            print(f"Verification FAILED: {verify_result.errors[0]}")
            sys.exit(1)
        print(f"Verified: {verify_result.triple_count:,} triples")

        # Generate VoID
        citation_text = render_citation(ds.get("citation", ""))
        void = generate_void(
            data_path=clean_ttl,
            dataset_id=dataset,
            title=ds["description"],
            license_uri="",
            source_uri=ds["source_url"],
            citation=citation_text,
            output_path=tmpdir / "_void.ttl",
        )
        print(f"Generated VoID: {void.triples:,} triples, {void.classes} classes")

        # Extract schema
        schema = extract_schema(data_path=clean_ttl)
        generate_schemas_yaml(schema, tmpdir / "_schema.yaml")
        print(f"Extracted schema: {len(schema.classes)} classes")

        # Schema diff (run before push, while both schemas are in memory)
        new_schema_path = tmpdir / "_schema.yaml"
        if old_schema and new_schema_path.exists():
            with open(new_schema_path) as f:
                new_schema = yaml.safe_load(f).get("classes", {})
            schema_diff = diff_schemas(old_schema, new_schema)
            print(f"{dataset} schema diff:")
            for name, count in schema_diff["added"]:
                print(f"  + Added class: {name} ({count} properties)")
            for name, old_count, new_count in schema_diff["changed"]:
                delta = new_count - old_count
                sign = "+" if delta > 0 else ""
                print(f"  ~ Changed class {name}: {sign}{delta} properties ({old_count} -> {new_count})")
            for name, count in schema_diff["removed"]:
                print(f"  - Removed class: {name} ({count} properties)  <- WARNING")
            if not schema_diff["added"] and not schema_diff["removed"] and not schema_diff["changed"]:
                print("  No changes.")

        # Push clean artifact
        annotations = {
            **build_annotations(ds, dataset),
            "org.opencontainers.image.version": version,
            "io.github.gillisandrew.linked-past.triples": str(verify_result.triple_count),
            "io.github.gillisandrew.linked-past.raw-digest": raw_digest,
        }

        files_to_push = [clean_ttl, tmpdir / "_void.ttl", tmpdir / "_schema.yaml"]

        digest = push_dataset(clean_ref, files_to_push, annotations=annotations)
        print(f"Pushed clean: {clean_ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: clean_dataset.py <dataset> [version]")
        sys.exit(1)
    dataset = sys.argv[1]
    version = sys.argv[2] if len(sys.argv) > 2 else "latest"
    main(dataset, version)
