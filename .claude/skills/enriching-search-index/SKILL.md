---
name: enriching-search-index
description: Use when search_entities cannot find entities by the names a scholar would use, when a dataset's labels are catalogue numbers or codes, when a label predicate is not being indexed, or when a dataset should contribute to the meta-entity index.
---

# Enriching the Search Index

## Overview

`search_entities` runs over an FTS5 index built at startup by
`_index_dataset` in `linked_past/core/server.py`. Most datasets are findable
with no work because their labels are names. Enrichment is for the rest:
labels that are codes, names that live under an unusual predicate, or
entities that need a word from another dataset to be searchable.

## When to Use

- Five representative searches (below) miss.
- A dataset's `skos:prefLabel` values look like `RRC 366/1` or `HD000001`.
- NOT for: cross-dataset identity links (use `entity-enrichment`); bad SPARQL (use `authoring-dataset-context`).

## How indexing works (read before changing anything)

Per dataset, `_index_dataset` adds:

1. `dataset`, `example`, `tip`, `schema_label`, `schema_comment`, `shex_shape` rows from the plugin's YAML.
2. `entity_label` rows, `"{label}\t{uri}"`, for every value of a fixed predicate list (`rdfs:label`, `skos:prefLabel`, `skos:altLabel`, `dcterms:title`, two Pleiades name predicates) plus every property in `schemas.yaml` whose `pred` name contains `name`, `label`, or `title`.
3. Rows returned by the plugin's `extra_search_entries(store, registry)` hook.
4. `skos_vocab` rows summarising each SKOS concept scheme.

The index is cached with a fingerprint. After changing anything above run:

```bash
uv run linked-past-server reindex
```

## Procedure

### 1. Diagnose with five searches

Pick five entities a scholar would search for, using the names they would
type (a person's cognomen, a place's ancient name, a coin's issuer). Run
`search_entities(query_text=<name>, dataset=<name>)` for each. Note which miss, then look at the
entity with `explore_entity` to see which predicate carries the name.

Without a running server, search the index directly:

```bash
uv run python - <<'EOF'
from linked_past.core.search import SearchIndex
from linked_past.core.store import get_data_dir
idx = SearchIndex(get_data_dir() / "search.db")
print(idx.search("<name>", dataset="<name>", doc_type="entity_label"))
EOF
```

### 2. Choose the fix

```
name is under a predicate not in the fixed list ->
    add that property to schemas.yaml with a pred name containing "name"/"label"/"title"
    (no code change; the indexer discovers it)

label needs a word from another dataset (issuer, findspot, period) ->
    implement extra_search_entries on the plugin

label needs a computed form from the same dataset (e.g. name without prefix) ->
    implement extra_search_entries; no registry lookup needed

name is reachable only through another node (person -> name node -> literal,
a label on a linked concept, any path longer than one predicate) ->
    implement extra_search_entries; a schemas.yaml `pred` names one hop and
    the indexer cannot follow a path
```

### 3. Implement the hook

Signature on `DatasetPlugin`:

```python
def extra_search_entries(self, store: Store, registry) -> list[tuple[str, str]]:
    """Return (doc_type, text) rows. text is f"{label}\t{uri}" for entity_label."""
```

Rules: return `[]` if `registry` is `None` or `registry.get_store(other)`
raises `KeyError` (the sibling dataset may not be installed); dedupe on
`(uri, label)`; log the row count. The worked example is
`linked_past/datasets/coin_types.py`, used by `crro/plugin.py` and
`ocre/plugin.py`: it joins each coin type's `nmo:hasIssuer` to the issuer's
English `skos:prefLabel` in the Nomisma store and emits
`"RRC 366/1 — C. Annius\t<coin uri>"`.

Keep the hook's queries cheap. It runs for every entity at every reindex;
one query for the batch plus one small lookup per row is the ceiling.

### 4. Test it

Follow `tests/test_coin_types.py`: build in-memory `pyoxigraph.Store`
objects from a few lines of Turtle, wrap them in a fake registry whose
`get_store` raises `KeyError` for missing names, and assert on the exact
rows. Add a case where the sibling store is absent and expect `[]`.

```bash
uv run pytest packages/linked-past/tests/test_<name>.py -q
```

### 5. Reindex and re-run the five searches

```bash
uv run linked-past-server reindex
```

Report which of the five now hit. Without a running server, use the
`SearchIndex` snippet from step 1 against `search.db` after reindexing.

## Meta-entity index

`meta_entities.db` clusters the same real-world entity across datasets. It is
seeded from the curated linkage YAML and Wikidata concordances, then extended
by dataset-specific bridges; the EDH bridge in
`linked_past/core/meta_entities.py` (`_extend_with_edh`) is the current
example. A new dataset joins the meta-entity index by contributing linkage
YAML (`entity-enrichment` skill) or Wikidata concordances; adding another
bridge in `meta_entities.py` is a code change and out of this skill's scope.
`_uri_to_dataset` there uses `DatasetRegistry._URI_NAMESPACES`, so the
dataset's namespace must be registered.

## Common Mistakes

- Indexing full text fields (inscription bodies, descriptions). They drown the label matches. The indexer deliberately excludes `editionText`.
- Enriching by editing `_index_dataset` with a dataset-name check. Use the hook.
- Forgetting `reindex`; the fingerprint cache serves the old index.
- A hook that raises when a sibling dataset is missing. The server logs and continues, but the enrichment silently disappears.
