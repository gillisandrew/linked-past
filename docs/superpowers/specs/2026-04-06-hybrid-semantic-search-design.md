# Hybrid Semantic Search for Context Corpus

**Date:** 2026-04-06
**Status:** Approved

## Problem

The current search infrastructure uses SQLite FTS5 with BM25 ranking. This works well for keyword matches but fails on conceptual/semantic queries. For example, "people involved in grain supply" won't match DPRR examples about `praefectus annonae` because there's no keyword overlap.

## Approach

Add a vector embedding layer alongside the existing FTS5 index, combining results via Reciprocal Rank Fusion (RRF). Inspired by [sparql-llm](https://github.com/sib-swiss/sparql-llm)'s RAG architecture, adapted to our MCP tool model.

## Scope

**In scope:**
- Embed the context corpus (dataset descriptions, examples, tips, schema comments, ShEx shapes, SKOS vocab/concept summaries)
- Hybrid BM25 + cosine search for `discover_datasets`
- sqlite-vec for vector storage in a separate `vec.db` alongside `search.db`
- FastEmbed with `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384-dim, ONNX)

**Out of scope (future extension):**
- Entity label embeddings (`search_entities` stays FTS5-only)
- Tool efficacy eval suite (deferred to a separate effort)
- Alternative embedding models or external vector stores

## Architecture

### New module: `core/vector.py`

`VectorIndex` class:
- Wraps sqlite-vec extension to store and query 384-dim float vectors
- Backed by a separate `vec.db` file alongside the FTS5 `search.db` (separate DBs because sqlite-vec and FTS5 virtual tables use different engines)
- Vectors are stored in a sqlite-vec virtual table with a foreign key (`rowid`) referencing the existing `documents` table
- Provides `add_batch(ids, vectors)` and `search(query_vector, k) -> list[(rowid, distance)]`
- The embedding model (`fastembed.TextEmbedding`) loads lazily on first use

### Hybrid search in `core/search.py`

New `hybrid_search()` function in `core/search.py` that takes a `SearchIndex` and `VectorIndex` and:
1. Runs BM25 search via existing FTS5 (returns `{rowid: bm25_score}`)
2. Runs cosine similarity via `VectorIndex` (returns `{rowid: cosine_score}`)
3. Combines via RRF: `score(d) = sum(1 / (k + rank_i(d)))` where `k=60` (standard constant) and `rank_i` is the document's rank in each result list
4. Returns unified results with the same `{dataset, doc_type, text, score}` shape

### Embedded document types

Only these `doc_type` values get vector embeddings:
- `dataset` — dataset descriptions
- `example` — SPARQL query examples (question + sparql)
- `tip` — query optimization tips
- `schema_comment` — class descriptions
- `shex_shape` — ShEx-like shape descriptions
Excluded (FTS5-only, keyword matching is sufficient):
- `entity_label` — entity labels (keyword precision matters; future extension)
- `schema_label` — short class labels (better served by exact match)
- `skos_vocab` — vocabulary summaries (keyword-rich, 164 docs)
- `skos_concept` — individual concept definitions (16K+ short label:definition pairs)

### Build pipeline changes in `server.py`

`_build_search_index()` gains a second phase after FTS5 indexing:
1. Query all documents with embeddable `doc_type` from the `documents` table
2. Batch-embed their `text` column via FastEmbed
3. Insert vectors into the sqlite-vec table via `VectorIndex.add_batch()`
4. Same fingerprint cache invalidation as FTS5 — if fingerprint matches, both indexes are reused

Fingerprint includes a schema version bump so first startup after this change triggers a rebuild.

### MCP tool integration

One tool switches to hybrid search:
- **`discover_datasets`** — uses hybrid search over the context corpus to match questions to datasets

Unchanged:
- **`get_schema`** — returns full ontology overview (no search involved). Future: could use hybrid search to surface relevant examples/tips.
- **`search_entities`** — remains FTS5-only (entity labels not embedded)

## Dependencies

Added to `packages/linked-past/pyproject.toml`:
- `fastembed` — ONNX-based text embedding (brings `onnxruntime` transitively)
- `sqlite-vec` — SQLite extension for vector similarity search

## Startup cost

- **One-time:** FastEmbed model download (~130MB cached in `.fastembed_cache`)
- **Per rebuild:** Embedding ~1000 documents takes ~2-5 seconds on CPU
- **Cached startup:** Zero additional cost (vectors persist in `vec.db`)

## Testing

Extend `test_search.py` with:
- `VectorIndex` unit tests (add, search, persistence)
- Hybrid search tests verifying that semantic queries (no keyword overlap) return relevant results
- Regression tests: existing BM25 test cases must still pass through the hybrid path

Integration tests (`conftest.py`) get `skip_search=True` behavior unchanged — vector index is part of the search index and skipped in the same way.

**Critical: No embedding model in tests.** The FastEmbed model must never load during `pytest`. The `VectorIndex` unit tests use pre-computed fixture vectors (hard-coded float arrays), not the actual embedding model. The embedding model is only instantiated in the build pipeline (`_build_search_index`), which is gated behind `skip_search=False` — and all test fixtures use `skip_search=True`. If any test needs to exercise hybrid search, it injects mock vectors directly into the sqlite-vec table.
