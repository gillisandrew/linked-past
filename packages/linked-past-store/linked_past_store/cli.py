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

    path = pull_dataset(args.ref, args.output)
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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
