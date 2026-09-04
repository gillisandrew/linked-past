---
name: authoring-dataset-context
description: Use when creating a dataset plugin package, writing or improving prefixes.yaml, schemas.yaml, examples.yaml, or tips.yaml, when a user reports the model writing bad SPARQL for a dataset, or when get_schema output for a dataset is thin.
---

# Authoring Dataset Context

## Overview

The four YAML files in a plugin's `context/` directory are everything the
model gets about a dataset: what classes exist, what predicates and value
shapes they have, worked queries, and the quirks that would otherwise cost a
failed query. Write them from the cleaned data, not from the upstream
ontology document. Then prove every example runs.

## When to Use

- New plugin package (after the clean stage has produced `_schema.yaml` and `_void.ttl`).
- A query the model wrote failed for a reason the data made predictable.
- `get_schema` for a dataset shows only auto-detected classes.
- NOT for: search misses by name (use `enriching-search-index`).

## Procedure

### 1. Get the data locally

```bash
uv run linked-past-server update <name>     # pulls clean artifact, builds store
ls "${LINKED_PAST_DATA_DIR:-$HOME/.local/share/linked-past}/<name>"   # <name>.ttl _void.ttl _schema.yaml
```

### 2. Create the plugin package

`packages/linked-past/linked_past/datasets/<name>/__init__.py` (empty),
`plugin.py`, and `context/` with the four files. Skeletons are in
`context-yaml-reference.md`. The `DatasetPlugin` class contract
(`datasets/base.py`) requires: `name`, `display_name`, `description`,
`citation`, `license`, `url`, `time_coverage`, `spatial_coverage`,
`oci_dataset = "datasets/<name>"`; the parametrized tests in
`tests/test_plugins.py::test_plugin_attributes` check the first five
(`name`, `license`, `display_name`, `description`, `url`). Do not override
`fetch` or `load` unless the dataset needs a different loading rule; the
base `load` already handles multi-file datasets, the ontology sidecar, and
materialization.

### Querying the store from the shell

Steps 3 and 4 both need to run SPARQL against the local store. Use this
snippet, substituting the query:

```bash
uv run python - <<'EOF'
from linked_past.core.store import get_read_only_store, get_data_dir
name = "<name>"
store = get_read_only_store(get_data_dir() / name / "store")
for row in store.query("""<QUERY>"""):
    print(row)
EOF
```

If the dataset has no OCI artifact yet, `get_read_only_store` has nothing to
open; the fallback is `pyoxigraph.Store().bulk_load(path=..., format=RdfFormat.TURTLE)`
against the Turtle file directly.

### 3. Write `prefixes.yaml` from the data

List every namespace that appears in the data with a short prefix. Verify
each one with a query rather than trusting the ontology documentation (run
with the snippet above):

```sparql
SELECT ?p (COUNT(*) AS ?n) WHERE { ?s ?p ?o } GROUP BY ?p ORDER BY DESC(?n) LIMIT 50
```

If a predicate lives under a versioned or unexpected namespace (EDH's
`http://lawd.info/ontology/1.0/foundAt`), keep the standard prefix for the
standard namespace and write a tip about the odd one.

### 4. Write `schemas.yaml` from `_schema.yaml` and VoID

Open `_schema.yaml` and `_void.ttl`. Hand-write only the classes a scholar
would ask about, typically three to eight. Long-tail classes stay in the
auto schema, which the registry merges in at load time. For each class:

- `uri` in prefixed form, `label`, and a `comment` that says what an
  instance is in this dataset's terms.
- Every property a query would plausibly touch, with `range` and a `comment`
  that describes what the values actually look like (`"string like '0071'"`,
  `"links to a Nomisma concept URI"`), because that is what the model needs
  to write a `FILTER`.

Check each property's real range (run with the snippet above):

```sparql
SELECT ?o WHERE { ?s a <ClassURI> ; <PredicateURI> ?o } LIMIT 5
```

### 5. Write `examples.yaml`

Each example is a `question` phrased the way a user would ask it, and a
`sparql` block that:

- declares every prefix it uses inline (examples are copied verbatim),
- targets one concept,
- ends with `LIMIT`,
- returns a human-readable label column, not only URIs.

Together the examples must touch every hand-written class; the validator
matches examples to queries by class. Aim for six to twelve.

### 6. Write `tips.yaml`

A tip is a fact that would otherwise cost the model a failed query. Sources:
every surprise you hit in steps 3 to 5. Typical tips: date encoding and how
to compare it, which label predicate carries language tags, predicates that
look like one ontology but are another, coverage gaps ("no inscriptions
before 50 BC"), which of two similar text fields to search. Tag each tip with
the `classes` it applies to; an empty list makes it a cross-cutting tip shown
in `get_schema`.

### 7. Verify

Run every example against the store and require rows:

```bash
uv run python - <<'EOF'
import yaml
from pathlib import Path
from linked_past.core.store import get_read_only_store, get_data_dir
name = "<name>"
store = get_read_only_store(get_data_dir() / name / "store")
examples = yaml.safe_load(Path(f"packages/linked-past/linked_past/datasets/{name}/context/examples.yaml").read_text())["examples"]
for ex in examples:
    rows = list(store.query(ex["sparql"]))
    print(f"{len(rows):5d}  {ex['question']}")
    assert rows, f"empty result: {ex['question']}"
EOF
```

Then:

```bash
uv run pytest packages/linked-past/tests/test_plugins.py -q
```

Then start the server, call `validate_sparql` with a deliberately wrong
query against one of your classes, and confirm your tips appear in the
response.

### 8. Register the plugin

The plugin is not done until it is registered; `discover_plugins()` finds
subclasses only through the import in `datasets/__init__.py`.
`datasets/__init__.py` import and `__all__`; `registry.py` `_URI_NAMESPACES`;
`tests/conftest.py` map; `tests/test_plugins.py` `PLUGIN_SPECS` with a
two-triple sample that instantiates one hand-written class.

## Common Mistakes

- Copying class lists from the ontology PDF. Half of them have zero instances.
- Property comments that restate the ontology ("the start date") instead of the value shape ("xsd:string like '-0044', zero-padded, negative is BC").
- Examples with a prefix used but not declared; they fail when copied.
- Examples without `LIMIT`; the model copies them and floods the viewer.
- Tips that are general SPARQL advice. If it is true of every dataset it is not a tip.
- Not tagging tips with classes, so they never surface during validation.
- Stopping after the YAML files. Two pressure runs wrote perfect context and left the plugin unregistered because "registration was out of scope". It is in scope.
