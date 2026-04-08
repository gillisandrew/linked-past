# Semantic Example Query Search

**Date:** 2026-04-08
**Status:** Approved
**Scope:** Replace class-name example matching with hybrid search in `validate_sparql`

## Problem

`validate_sparql` retrieves relevant example queries via rigid class-name matching: it extracts RDF classes from the user's SPARQL, then finds examples whose classes overlap. This misses structurally similar examples when class names don't exactly match (e.g., a query using `dprr:PostAssertion` patterns won't match examples that demonstrate `dprr:TribeAssertion` patterns, even though the assertion structure is identical).

## Solution

Replace example retrieval with `hybrid_search()` using the user's SPARQL as the search query. The infrastructure already exists — example queries are indexed in FTS5 and embedded in the vector index at startup. The hybrid search combines BM25 (shared keywords like class names, predicates) with cosine similarity (structural query patterns).

Tips retrieval stays class-based — tips are prescriptive guidance tied to specific classes.

## Changes to `validate_sparql`

Currently (server.py ~line 802-833), after validation the tool calls `plugin.get_relevant_context(fixed_sparql)` which internally calls both `get_relevant_examples()` and `get_relevant_tips()`.

New flow:

1. **Semantic example search** (when `app.search` is available): call `hybrid_search(fixed_sparql, query_vector, app.search, app.vector, k=3, dataset=dataset, doc_type="example")`. The results contain the full example text (question + SPARQL). Format as markdown.

2. **Class-based tip search** (unchanged): call `plugin.get_relevant_tips(class_names)` using the extracted class names. Tips are prescriptive and class-specific, so exact matching is appropriate.

3. **Fallback** (when `app.search` is `None`): fall back to the existing `plugin.get_relevant_context(fixed_sparql)` which uses class-name matching for both examples and tips. This preserves behavior in test environments and cold starts where the search index isn't built.

## Interface Changes

### `DatasetPlugin` (base.py)

Add a new method:

```python
def get_relevant_tips(self, sparql: str) -> str:
```

Extracts classes from the SPARQL, matches tips via the existing class-based logic, and returns rendered markdown. This is the tips-only half of the current `get_relevant_context()`.

The existing `get_relevant_context()` method stays unchanged as the fallback path.

### `validate_sparql` tool (server.py)

The tool gains access to `app.search`, `app.vector`, and `app.embedder` (already on `AppContext`). When available, it uses hybrid search for examples and the plugin method for tips. When not available, falls back to `get_relevant_context()`.

## What Does NOT Change

- Example YAML format, loading, or indexing (already indexed at startup)
- `hybrid_search()` function (already exists in `search.py`)
- Embedder initialization (already lazy-loaded)
- `search_entities` and `discover_datasets` usage of hybrid search
- The `query` tool (does not return context — that's `validate_sparql`'s job)
- Test behavior with `skip_search=True` (falls back to class matching)

## Files to Modify

| File | Change |
|------|--------|
| `linked_past/core/server.py` | `validate_sparql` tool: use hybrid search for examples when available |
| `linked_past/datasets/base.py` | Add `get_relevant_tips()` method (tips-only extraction from existing logic) |
