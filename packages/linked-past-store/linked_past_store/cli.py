"""CLI for linked-past-store."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def cmd_push(args):
    from linked_past_store.push import push_dataset

    annotations = {}
    if args.license:
        annotations["org.opencontainers.image.licenses"] = args.license
    if args.citation:
        annotations["dev.linked-past.citation"] = args.citation
    if args.source:
        annotations["org.opencontainers.image.source"] = args.source

    digest = push_dataset(args.ref, args.file, annotations=annotations)
    print(f"Pushed {args.ref}")
    if digest:
        print(f"Digest: {digest}")


def cmd_pull(args):
    from linked_past_store.pull import pull_dataset

    path = pull_dataset(args.ref, args.output, force=args.force)
    print(f"Pulled to {path}")


def cmd_sanitize(args):
    from linked_past_store.sanitize import sanitize_turtle

    result = sanitize_turtle(args.input, args.output)
    print(f"Applied {result.fixes_applied} fixes")
    print(f"Output: {result.output_path} ({result.output_size:,} bytes)")


def cmd_verify(args):
    from linked_past_store.verify import verify_turtle

    result = verify_turtle(args.file)
    if result.ok:
        print(f"OK: {result.triple_count:,} triples ({result.format})")
    else:
        print(f"FAILED: {result.errors[0]}")
        sys.exit(1)


def cmd_inspect(args):
    result = subprocess.run(
        ["oras", "manifest", "fetch", args.ref],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    manifest = json.loads(result.stdout)
    annotations = manifest.get("annotations", {})
    if annotations:
        print(f"Annotations for {args.ref}:\n")
        for key, val in sorted(annotations.items()):
            print(f"  {key}: {val}")
    else:
        print(f"No annotations found for {args.ref}")


def cmd_cache_list(args):
    from linked_past_store.cache import ArtifactCache

    cache = ArtifactCache()
    entries = cache.list_cached()
    if not entries:
        print("Cache is empty.")
        return
    print(f"{'Digest':24s} {'Files':>5s} {'Size':>10s}  Last Accessed")
    print("-" * 65)
    for e in entries:
        digest = e["digest"][:24]
        size = f"{e['size_bytes'] / 1024 / 1024:.1f} MB"
        print(f"{digest} {e['files']:5d} {size:>10s}  {e['last_accessed']}")


def cmd_cache_gc(args):
    from linked_past_store.cache import ArtifactCache

    cache = ArtifactCache()
    removed = cache.gc(max_age_days=args.max_age)
    print(f"Removed {removed} cached artifacts older than {args.max_age} days")


def cmd_cache_clear(args):
    import shutil

    from linked_past_store.cache import ArtifactCache

    cache = ArtifactCache()
    if cache._blobs_dir.exists():
        shutil.rmtree(cache._blobs_dir)
    if cache._layers_dir.exists():
        shutil.rmtree(cache._layers_dir)
    if cache._manifests_dir.exists():
        shutil.rmtree(cache._manifests_dir)
    if cache._gc_path.exists():
        cache._gc_path.unlink()
    print("Cache cleared.")


def cmd_ontology_extract(args):
    from pathlib import Path

    from linked_past_store.ontology import extract_schema, generate_schemas_yaml

    ontology_path = Path(args.ontology) if args.ontology else None
    data_path = Path(args.from_data) if args.from_data else None
    output = Path(args.output)

    prefix_map = {}
    if args.prefix:
        for p in args.prefix:
            ns, short = p.split("=", 1)
            prefix_map[ns] = short

    schema = extract_schema(ontology_path=ontology_path, data_path=data_path)
    generate_schemas_yaml(schema, output, prefix_map=prefix_map or None)
    print(f"Wrote {len(schema.classes)} classes to {output}")


def cmd_void_generate(args):
    from pathlib import Path

    from linked_past_store.void import generate_void

    void = generate_void(
        data_path=args.data,
        dataset_id=args.dataset_id,
        title=args.title,
        license_uri=args.license or "",
        source_uri=args.source or "",
        citation=args.citation or "",
        publisher=args.publisher or "",
        output_path=Path(args.output) if args.output else None,
    )

    print(f"Dataset: {void.title}")
    print(f"  Triples:    {void.triples:,}")
    print(f"  Entities:   {void.entities:,}")
    print(f"  Classes:    {void.classes}")
    print(f"  Properties: {void.properties}")
    print(f"  URI space:  {void.uri_space}")
    if args.output:
        print(f"  Written to: {args.output}")
    else:
        print(void.to_turtle())


def cmd_bom(args):
    """Generate a Bill of Materials for all cached/used datasets."""
    from linked_past_store.cache import ArtifactCache

    cache = ArtifactCache()

    # Collect BOM entries from manifest tag files
    bom = []
    if cache._manifests_dir.exists():
        for tag_file in sorted(cache._manifests_dir.rglob("*")):
            if not tag_file.is_file():
                continue
            digest = tag_file.read_text().strip()
            # Reconstruct ref from path
            rel = tag_file.relative_to(cache._manifests_dir)
            parts = list(rel.parts)
            tag = parts[-1]
            repo = "/".join(parts[:-1])
            ref = f"{repo}:{tag}"

            # Try to get annotations
            annotations = {}
            try:
                result = subprocess.run(
                    ["oras", "manifest", "fetch", ref],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    manifest = json.loads(result.stdout)
                    annotations = manifest.get("annotations", {})
            except Exception:
                pass

            bom.append({
                "ref": ref,
                "digest": digest,
                "license": annotations.get("org.opencontainers.image.licenses", "unknown"),
                "description": annotations.get("org.opencontainers.image.description", ""),
                "version": annotations.get("org.opencontainers.image.version", tag),
                "source": annotations.get("org.opencontainers.image.source", ""),
                "citation": annotations.get("dev.linked-past.citation", ""),
            })

    if not bom:
        print("No datasets in cache. Pull some first with `linked-past-store pull`.")
        return

    if args.format == "json":
        print(json.dumps(bom, indent=2))
    else:
        # Markdown table
        print("# Data Bill of Materials\n")
        print(f"**Generated:** {__import__('datetime').datetime.now().isoformat()}\n")
        print("| Dataset | Version | Digest | License | Citation |")
        print("|---------|---------|--------|---------|----------|")
        for entry in bom:
            ref = entry["ref"].rsplit("/", 1)[-1].split(":")[0] if "/" in entry["ref"] else entry["ref"]
            digest = entry["digest"][:20] + "..."
            print(f"| {ref} | {entry['version']} | `{digest}` | {entry['license']} | {entry['citation'][:40]} |")
        print("\nAll artifacts stored at content-addressable digests.")
        print("To reproduce, pull each artifact by digest:")
        print("```")
        for entry in bom:
            repo = entry["ref"].rsplit(":", 1)[0]
            print(f"linked-past-store pull {repo}@{entry['digest']}")
        print("```")


def main():
    parser = argparse.ArgumentParser(
        prog="linked-past-store",
        description="Distribute scholarly RDF datasets as OCI artifacts",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # push
    p = sub.add_parser("push", help="Push an RDF file to an OCI registry")
    p.add_argument("ref", help="OCI reference (e.g., ghcr.io/myorg/dataset:v1.0)")
    p.add_argument("file", help="Path to the RDF file")
    p.add_argument("--license", help="SPDX license identifier")
    p.add_argument("--citation", help="Scholarly citation")
    p.add_argument("--source", help="Upstream source URL")
    p.set_defaults(func=cmd_push)

    # pull
    p = sub.add_parser("pull", help="Pull an RDF dataset from an OCI registry")
    p.add_argument("ref", help="OCI reference")
    p.add_argument("--output", "-o", default=".", help="Output directory")
    p.add_argument("--force", "-f", action="store_true", help="Bypass cache, re-download from registry")
    p.set_defaults(func=cmd_pull)

    # sanitize
    p = sub.add_parser("sanitize", help="Sanitize RDF for strict parsers")
    p.add_argument("input", help="Input RDF file")
    p.add_argument("--output", "-o", help="Output file (default: overwrite input)")
    p.set_defaults(func=cmd_sanitize)

    # verify
    p = sub.add_parser("verify", help="Verify RDF loads into Oxigraph")
    p.add_argument("file", help="RDF file to verify")
    p.set_defaults(func=cmd_verify)

    # inspect
    p = sub.add_parser("inspect", help="Show OCI manifest annotations")
    p.add_argument("ref", help="OCI reference")
    p.set_defaults(func=cmd_inspect)

    # cache
    cache_parser = sub.add_parser("cache", help="Manage the local artifact cache")
    cache_sub = cache_parser.add_subparsers(dest="cache_command", required=True)

    cache_sub.add_parser("list", help="List cached artifacts").set_defaults(func=cmd_cache_list)

    p = cache_sub.add_parser("gc", help="Remove old cached artifacts")
    p.add_argument("--max-age", type=int, default=30, help="Max age in days (default: 30)")
    p.set_defaults(func=cmd_cache_gc)

    cache_sub.add_parser("clear", help="Clear entire cache").set_defaults(func=cmd_cache_clear)

    # bom
    p = sub.add_parser("bom", help="Generate a Bill of Materials for datasets used")
    p.add_argument("--format", "-f", choices=["markdown", "json"], default="markdown", help="Output format")
    p.set_defaults(func=cmd_bom)

    # ontology
    onto_parser = sub.add_parser("ontology", help="Extract schema from ontology or data")
    onto_sub = onto_parser.add_subparsers(dest="ontology_command", required=True)

    p = onto_sub.add_parser("extract", help="Extract schema to YAML")
    p.add_argument("ontology", nargs="?", help="OWL/RDFS ontology file")
    p.add_argument("--from-data", help="RDF data file for empirical extraction")
    p.add_argument("--output", "-o", default="schemas.yaml", help="Output YAML file")
    p.add_argument("--prefix", action="append", help="Prefix mapping: namespace=short")
    p.set_defaults(func=cmd_ontology_extract)

    # void
    void_parser = sub.add_parser("void", help="Generate VoID dataset descriptions")
    void_sub = void_parser.add_subparsers(dest="void_command", required=True)

    p = void_sub.add_parser("generate", help="Generate VoID from data")
    p.add_argument("data", help="RDF data file")
    p.add_argument("--dataset-id", required=True, help="Short dataset identifier")
    p.add_argument("--title", required=True, help="Human-readable dataset title")
    p.add_argument("--license", help="License URI")
    p.add_argument("--source", help="Upstream source URL")
    p.add_argument("--citation", help="Bibliographic citation")
    p.add_argument("--publisher", help="Publisher name")
    p.add_argument("--output", "-o", help="Output file (prints to stdout if omitted)")
    p.set_defaults(func=cmd_void_generate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
