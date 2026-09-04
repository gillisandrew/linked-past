---
name: cleaning-rdf-dumps
description: Use when a dataset's Turtle fails strict parsing, validate_dataset fails, the triple count is under threshold, the schema diff shows unexpected churn, or a new dataset is being cleaned for the first time. Covers classifying upstream data breakage and deciding which pipeline stage owns the fix.
---

# Cleaning RDF Dumps

## Overview

Upstream scholarly datasets are not written for strict parsers. The clean
stage (`scripts/clean_dataset.py`) turns the raw artifact into one that
pyoxigraph loads without error, plus VoID and schema sidecars. When it
fails, the job is to classify the breakage and fix it at the earliest stage
that owns that kind of problem. Never hand-edit an artifact.

## When to Use

- `clean_dataset` or `validate_dataset` exits non-zero.
- `verify_turtle` reports errors for a file the ingest produced.
- The schema diff printed by `clean_dataset` shows classes vanishing.
- NOT for: download or conversion failures before a Turtle file exists (use `ingesting-rdf-source`).

## Procedure

### 1. Reproduce with a strict parse and capture the first error

```bash
uv run python - <<'EOF'
from linked_past_store import verify_turtle
r = verify_turtle("scratch/<name>.ttl")
print(r.triple_count)
for e in r.errors: print(e)
EOF
```

pyoxigraph errors name a line and column. Look at that line:

```bash
sed -n '<line-2>,<line+2>p' scratch/<name>.ttl
```

### 2. Classify the breakage

| Level | Symptom | Owner |
|-------|---------|-------|
| XML | The XML parser fails before RDF is considered (undefined entity, bad UTF-8) | Ingest script (`ingesting-rdf-source`) |
| IRI | Valid XML, IRI violates RFC 3987 (spaces, placeholder `-`, U+FFFD, missing scheme) | Ingest script when source-specific; `sanitize.py` when any Turtle could have it |
| Turtle | Valid RDF/XML, strict Turtle parser rejects (language subtag over 8 chars, percent-encoded `#`) | `linked_past_store/sanitize.py` `_regex_fixes` |
| Semantic | Parses, but the triples are wrong (dangling references, duplicate literals, wrong namespace) | Ingest script for reference repair; schema YAML for namespace; `store.materialize` for inference artifacts |

Look the symptom up in `issue-catalog.md` before writing a fix. Most have
been seen before and the fix already exists in one of those files.

### 3. Fix at the owning stage

- `sanitize.py`: add a compiled regex and apply it in `_regex_fixes`; return the count so `SanitizeResult.fixes_applied` stays accurate. Add a test in `packages/linked-past-store/tests/`.
- Ingest script: apply the fix to the raw text before push and print the count.
- Never edit the Turtle by hand, and never commit a patched artifact. The next upstream release must go through the same code.

### 4. Re-run and record counts

`clean_dataset` pulls raw, sanitizes, verifies, prints the fix count and
schema diff, and pushes to `clean_ref` — all unconditionally in the same
run, with no dry-run flag. Confirm with the user before running the
command, not after the diff prints: by the time the diff is visible the
push has already happened.

```bash
uv run python -m scripts.clean_dataset <name>       # confirm first: this run also pushes clean
uv run python -m scripts.validate_dataset <name>
```

`clean_dataset` prints the number of fixes and the schema diff against the
previous version. Copy the fix count into the `docs/data-lifecycle.md`
catalog row so the next release can be compared.

When `rapper` is not installed, `sanitize_turtle` takes the regex-only path
(input must already be Turtle) and reports `triple_count=0`; take the count
from `verify_turtle` instead.

### 5. Set the threshold

`min_triple_count` in `datasets.yaml` should be about 90% of the verified
count, rounded down to a clean number. Too tight fails on harmless upstream
edits; too loose lets a truncated download through.

### 6. Read the schema diff

The diff prints after the push has already happened, so this is a post-hoc
check, not a gate. Removed classes or a class whose count fell by more than
half almost always mean a conversion error, not an upstream change — fix
the cause and re-run (which re-pushes and replaces the bad clean artifact).

### 7. Catalog it

Any breakage class not already in `docs/data-lifecycle.md` gets a row in the
matching table (XML, IRI, Turtle, semantic) in the same change as the fix.

## Rules

- Fix at the earliest stage that owns the quirk; a generic fix in `sanitize.py` runs for every dataset, so it must be safe for all of them.
- Every fix prints or returns a count.
- Strict parse after every fix. Lenient tools (`rapper`) hide problems; pyoxigraph is the arbiter.

## Common Mistakes

- Using `sed` on the artifact and moving on. The fix vanishes on the next ingest.
- Putting a Pleiades-only IRI repair into `sanitize.py`, where it runs against every dataset.
- Replacing an over-long language tag with `@en` instead of a private-use tag, losing information.
- Treating a lower triple count as "upstream shrank" without checking the schema diff.
