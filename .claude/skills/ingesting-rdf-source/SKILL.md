---
name: ingesting-rdf-source
description: Use when writing or changing an ingest script, adding a datasets.yaml entry, pushing a raw dataset artifact to the OCI registry, or setting up a scheduled ingest workflow for an RDF source (Turtle, RDF/XML, JSON-LD, N3, tarball, SPARQL endpoint).
---

# Ingesting an RDF Source

## Overview

Ingest turns an upstream publication into one raw Turtle file on the OCI
registry at `raw_ref`. It owns only source-format-specific fixes. Anything that
would apply to any Turtle file belongs to the clean stage.

## When to Use

- New dataset: no `datasets.yaml` entry yet.
- Upstream changed packaging (new URL, new format, new tarball layout).
- Ingest fails before a Turtle file exists (download, XML parse, conversion).
- NOT for: Turtle that exists but fails strict verification (use `cleaning-rdf-dumps`).

## Procedure

### 1. Pick the ingest path

```
single RDF/XML, JSON-LD, or Turtle URL     -> scripts/ingest_generic.py, no new code
tarball / zip / multi-file directory        -> bespoke scripts/ingest_<name>.py
SPARQL endpoint                             -> scripts/extract_from_endpoint.py pattern, then bespoke push
N3 or wrong namespaces                      -> convert_n3_to_ttl.py / rebind_prefixes.py, then bespoke push
upstream republishes on a schedule          -> also add .github/workflows/ingest-<name>.yml
```

Recipes for each are in `source-recipes.md`.

### 2. Add the `datasets.yaml` entry

Required for every dataset:

```yaml
<name>:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/<name>:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/<name>:latest
  ingest_script: scripts/ingest_<name>.py        # or scripts/ingest_generic.py
  min_triple_count: 0                             # set after first clean run
  license: <SPDX id>
  source_url: <landing page>
  description: "<one line, shown in discover_datasets>"
  citation: |
    @misc{...}
```

Add for the generic script: `fetch_url` and `source_format` (`rdf-xml`, `json-ld`, `turtle`).
Add `ontology_url` when the data uses an external ontology whose axioms
matter for inference (CRRO, OCRE, RPC point at `http://nomisma.org/ontology.ttl`).

`scripts/pipeline_config.py` reads this file. `build_annotations(ds, name)`
turns it into OCI annotations; do not construct annotations by hand.

### 3. Dry run without pushing

Never push on the first run. Download and convert into a scratch directory,
then inspect:

```bash
uv run python - <<'EOF'
from pathlib import Path
from linked_past_store import verify_turtle
r = verify_turtle(Path("scratch/<name>.ttl"))
print(r.triple_count, r.errors[:3])
EOF
head -c 2000 scratch/<name>.ttl
grep -c '^<' scratch/<name>.ttl      # rough subject count
```

For the generic script, the cheapest dry run is to call its conversion
steps in a REPL or to temporarily point `raw_ref` at a local registry.
For bespoke scripts, structure `main()` so the push is the final statement
and can be skipped with an environment variable or a `--no-push` argument.

Record the triple count. `min_triple_count` will be set to about 90% of it
in the clean stage.

### 4. Push the raw artifact

Pushing is an outward-facing side effect. Confirm with the user first, then:

```bash
uv run python -m scripts.ingest_<name>          # or: -m scripts.ingest_generic <name>
```

`push_dataset(ref, path, annotations=...)` from `linked_past_store` does the
upload and returns the digest. It needs registry credentials (`oras login ghcr.io`).

### 5. Optional: scheduled workflow

Copy `.github/workflows/ingest-pleiades.yml`. Keep `workflow_dispatch` so it
can be run by hand, set `permissions: packages: write`, and log in with
`oras login ghcr.io` using `GITHUB_TOKEN`.

## Rules

- Ingest owns source-format fixes only: XML entities, IRI whitespace, placeholder IRIs, wrong namespaces, tarball concatenation. Generic Turtle fixes go in `linked_past_store/sanitize.py`.
- Send `User-Agent: linked-past/1.0`; some hosts block Python's default agent with HTTP 403.
- Keep the raw artifact as close to upstream as parses. The clean stage records what it changed; ingest changes are invisible downstream unless the script prints counts.
- Print the count of every fix applied so it can be compared on the next upstream release.

## Common Mistakes

- Converting RDF/XML with lenient tools and never running a strict parse, so breakage surfaces in the clean stage with no line numbers.
- Hand-writing OCI annotations instead of `build_annotations`.
- Pushing a test run to `raw_ref:latest`, which the next clean run will pick up.
