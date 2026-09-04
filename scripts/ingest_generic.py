"""Generic dataset ingest: download from fetch_url, convert to Turtle, push to raw OCI.

Usage: ingest_generic.py <dataset> [--no-push [--out <turtle path>]]
"""

import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from linked_past_store import push_dataset

from scripts.pipeline_config import build_annotations, load_dataset_config

_DOCTYPE = '<!DOCTYPE rdf:RDF [<!ENTITY nbsp "&#160;">]>'
_XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>")
# rdf:resource / rdf:about values that start with a hostname instead of a scheme,
# e.g. rdf:resource="www.wikidata.org/entity/Q1". rapper would resolve these
# against the file's base IRI and emit file:/// junk.
_SCHEMELESS_IRI = re.compile(
    r'(rdf:(?:resource|about)=")((?:[a-z0-9-]+\.)+[a-z]{2,}/[^"]*)(")'
)


def prepare_rdfxml(text: str) -> tuple[str, dict[str, int]]:
    """Apply source-format fixes to RDF/XML before handing it to rapper.

    1. Inject a DOCTYPE declaring ``&nbsp;`` directly after the XML declaration
       (or at the top when there is none) so files using HTML entities parse.
       The declaration and the root element may share a line (Kerameikos), so
       this cannot be done by line.
    2. Prefix ``http://`` onto rdf:resource/rdf:about values that start with a
       hostname rather than a scheme.

    Returns the fixed text and a count of each fix applied.
    """
    fixes = {"schemeless_iris": 0}

    m = _XML_DECL.match(text)
    if m:
        text = text[: m.end()] + "\n" + _DOCTYPE + "\n" + text[m.end() :].lstrip("\r\n")
    else:
        text = _DOCTYPE + "\n" + text

    def _add_scheme(match: re.Match) -> str:
        fixes["schemeless_iris"] += 1
        return f"{match.group(1)}http://{match.group(2)}{match.group(3)}"

    text = _SCHEMELESS_IRI.sub(_add_scheme, text)
    return text, fixes


def main(dataset: str, push: bool = True, out_path: Path | None = None):
    ds = load_dataset_config(dataset)

    fetch_url = ds.get("fetch_url")
    source_format = ds.get("source_format")
    if not fetch_url or not source_format:
        print(f"ERROR: {dataset} requires fetch_url and source_format for generic ingest")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Download
        print(f"Downloading {fetch_url}...")
        raw_path = tmpdir / f"{dataset}_raw"
        req = urllib.request.Request(fetch_url, headers={"User-Agent": "linked-past/1.0"})
        with urllib.request.urlopen(req) as resp, open(raw_path, "wb") as out:
            out.write(resp.read())
        print(f"Downloaded ({raw_path.stat().st_size:,} bytes)")

        # Convert to Turtle
        ttl_path = tmpdir / f"{dataset}.ttl"
        if source_format == "rdf-xml":
            # Source-format fixes (DOCTYPE for HTML entities, scheme-less IRIs).
            fixed_path = tmpdir / f"{dataset}_fixed.rdf"
            fixed_text, fixes = prepare_rdfxml(raw_path.read_text(encoding="utf-8"))
            fixed_path.write_text(fixed_text, encoding="utf-8")
            for name, count in fixes.items():
                print(f"Fix {name}: {count}")

            print("Converting RDF/XML to Turtle via rapper...")
            with open(ttl_path, "w") as ttl_out:
                subprocess.run(
                    ["rapper", "-i", "rdfxml", "-o", "turtle", str(fixed_path)],
                    stdout=ttl_out,
                    stderr=subprocess.PIPE,
                    check=True,
                )
        elif source_format == "json-ld":
            print("Converting JSON-LD to Turtle via rdflib...")
            from rdflib import Graph

            g = Graph()
            g.parse(str(raw_path), format="json-ld")
            g.serialize(str(ttl_path), format="turtle")
        elif source_format == "turtle":
            shutil.copy2(raw_path, ttl_path)
        else:
            print(f"ERROR: Unknown source_format {source_format!r}")
            sys.exit(1)

        print(f"Created {ttl_path.name} ({ttl_path.stat().st_size:,} bytes)")

        if not push:
            if out_path:
                shutil.copy2(ttl_path, out_path)
                print(f"Dry run: wrote {out_path} (not pushed)")
            else:
                print("Dry run: not pushed")
            return

        # Push raw
        annotations = {
            **build_annotations(ds, dataset),
            "io.github.gillisandrew.linked-past.source-url": fetch_url,
        }
        ref = ds["raw_ref"]
        digest = push_dataset(ref, ttl_path, annotations=annotations)
        print(f"Pushed raw: {ref}")
        if digest:
            print(f"Digest: {digest}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: ingest_generic.py <dataset> [--no-push [--out <turtle path>]]")
        sys.exit(1)
    push = "--no-push" not in args
    out = Path(args[args.index("--out") + 1]) if "--out" in args else None
    main(args[0], push=push, out_path=out)
