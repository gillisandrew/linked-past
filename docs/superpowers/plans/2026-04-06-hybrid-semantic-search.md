# Hybrid Semantic Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add vector embeddings alongside FTS5 in the search index so `discover_datasets` handles conceptual/semantic queries that BM25 misses.

**Architecture:** New `VectorIndex` class wraps sqlite-vec in the existing `search.db`. A `hybrid_search()` function combines BM25 + cosine via Reciprocal Rank Fusion. FastEmbed (`intfloat/multilingual-e5-small`, 384-dim ONNX) generates vectors at index build time and for queries at runtime. The embedding model never loads during tests.

**Tech Stack:** sqlite-vec, fastembed, SQLite FTS5 (existing)

**Spec:** `docs/superpowers/specs/2026-04-06-hybrid-semantic-search-design.md`

---

### Task 1: Add dependencies

**Files:**
- Modify: `packages/linked-past/pyproject.toml`

- [ ] **Step 1: Add fastembed and sqlite-vec to dependencies**

In `packages/linked-past/pyproject.toml`, add to the `dependencies` list:

```toml
dependencies = [
    "pyoxigraph",
    "rdflib",
    "pyyaml",
    "mcp",
    "toons>=0.5.3",
    "markdown",
    "websockets",
    "linked-past-store",
    "reasonable",
    "fastembed",
    "sqlite-vec",
]
```

- [ ] **Step 2: Lock and install**

Run: `uv sync`
Expected: resolves and installs both packages without conflict.

- [ ] **Step 3: Verify imports work**

Run: `uv run python -c "import sqlite_vec; from fastembed import TextEmbedding; print('ok')"`
Expected: prints `ok`

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past/pyproject.toml uv.lock
git commit -m "build: add fastembed and sqlite-vec dependencies"
```

---

### Task 2: VectorIndex class with tests

**Files:**
- Create: `packages/linked-past/linked_past/core/vector.py`
- Create: `packages/linked-past/tests/test_vector.py`

- [ ] **Step 1: Write failing tests for VectorIndex**

Create `packages/linked-past/tests/test_vector.py`:

```python
"""Tests for the sqlite-vec vector index. Uses pre-computed fixture vectors — no embedding model."""

import math

from linked_past.core.vector import VectorIndex


def _make_vector(seed: float, dim: int = 384) -> list[float]:
    """Deterministic fixture vector. Not meaningful embeddings — just for testing storage/retrieval."""
    import hashlib
    h = hashlib.sha256(f"{seed}".encode()).digest()
    base = [b / 255.0 for b in h]
    # Repeat to fill dimension
    vec = (base * (dim // len(base) + 1))[:dim]
    return vec


def test_add_and_search():
    idx = VectorIndex()
    v1 = _make_vector(1.0)
    v2 = _make_vector(2.0)
    v3 = _make_vector(99.0)
    idx.add_batch([1, 2, 3], [v1, v2, v3])

    # Searching with v1 should return id=1 as closest
    results = idx.search(v1, k=3)
    assert len(results) == 3
    assert results[0][0] == 1  # (rowid, distance)
    assert results[0][1] < 0.01  # near-zero distance for identical vector


def test_search_empty():
    idx = VectorIndex()
    v = _make_vector(1.0)
    results = idx.search(v, k=5)
    assert results == []


def test_persistence(tmp_path):
    db_path = tmp_path / "vec.db"
    v1 = _make_vector(1.0)
    v2 = _make_vector(2.0)

    idx = VectorIndex(db_path=db_path)
    idx.add_batch([1, 2], [v1, v2])
    idx.close()

    idx2 = VectorIndex(db_path=db_path)
    results = idx2.search(v1, k=2)
    assert len(results) == 2
    assert results[0][0] == 1
    idx2.close()


def test_clear():
    idx = VectorIndex()
    v1 = _make_vector(1.0)
    idx.add_batch([1], [v1])

    idx.clear()
    results = idx.search(v1, k=5)
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_vector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'linked_past.core.vector'`

- [ ] **Step 3: Implement VectorIndex**

Create `packages/linked-past/linked_past/core/vector.py`:

```python
"""sqlite-vec backed vector index for semantic search."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import sqlite_vec

logger = logging.getLogger(__name__)

VECTOR_DIM = 384


class VectorIndex:
    """Cosine-similarity vector search using sqlite-vec."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            self._conn = sqlite3.connect(":memory:")
        else:
            self._conn = sqlite3.connect(str(db_path))

        self._conn.enable_load_extension(True)
        sqlite_vec.load(self._conn)
        self._conn.enable_load_extension(False)

        self._conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_documents USING vec0("
            f"  doc_id INTEGER PRIMARY KEY,"
            f"  embedding float[{VECTOR_DIM}] distance_metric=cosine"
            f")"
        )
        self._conn.commit()

    def add_batch(self, ids: list[int], vectors: list[list[float]]) -> None:
        """Insert document vectors. ids correspond to rowids in the FTS5 documents table."""
        rows = [
            (doc_id, sqlite_vec.serialize_float32(vec))
            for doc_id, vec in zip(ids, vectors)
        ]
        self._conn.executemany(
            "INSERT INTO vec_documents(doc_id, embedding) VALUES (?, ?)",
            rows,
        )
        self._conn.commit()
        logger.debug("indexed %d vectors", len(rows))

    def search(self, query_vector: list[float], k: int = 10) -> list[tuple[int, float]]:
        """Return top-k nearest neighbors as (doc_id, cosine_distance) pairs."""
        try:
            rows = self._conn.execute(
                "SELECT doc_id, distance FROM vec_documents "
                "WHERE embedding MATCH ? AND k = ? "
                "ORDER BY distance",
                [sqlite_vec.serialize_float32(query_vector), k],
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [(int(row[0]), float(row[1])) for row in rows]

    def clear(self) -> None:
        """Remove all vectors."""
        self._conn.execute("DELETE FROM vec_documents")
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_vector.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/vector.py packages/linked-past/tests/test_vector.py
git commit -m "feat: add VectorIndex class backed by sqlite-vec"
```

---

### Task 3: Hybrid search function with tests

**Files:**
- Modify: `packages/linked-past/linked_past/core/search.py`
- Modify: `packages/linked-past/tests/test_search.py`

- [ ] **Step 1: Write failing tests for hybrid_search**

Append to `packages/linked-past/tests/test_search.py`:

```python
from linked_past.core.search import hybrid_search
from linked_past.core.vector import VectorIndex


def _make_vector(seed: float, dim: int = 384) -> list[float]:
    """Deterministic fixture vector."""
    import hashlib
    h = hashlib.sha256(f"{seed}".encode()).digest()
    base = [b / 255.0 for b in h]
    return (base * (dim // len(base) + 1))[:dim]


def test_hybrid_rrf_combines_results():
    """Both BM25 and vector results contribute to final ranking via RRF."""
    fts = SearchIndex()
    vec = VectorIndex()

    # Doc 1: good BM25 match, mediocre vector match
    id1 = fts.add("dprr", "example", "consul office holding")
    # Doc 2: poor BM25 match, good vector match
    id2 = fts.add("dprr", "example", "magistrate administration role")

    v1 = _make_vector(1.0)
    v2 = _make_vector(2.0)
    vec.add_batch([id1, id2], [v1, v2])

    # Query that matches doc 1 by keywords
    results = hybrid_search(
        query="consul",
        query_vector=v1,  # close to doc 1's vector
        search_index=fts,
        vector_index=vec,
        k=5,
    )
    assert len(results) >= 1
    # Doc 1 should rank first (strong in both)
    assert results[0]["text"] == "consul office holding"

    fts.close()
    vec.close()


def test_hybrid_fts_only_fallback():
    """When vector_index is None, hybrid_search falls back to FTS5-only."""
    fts = SearchIndex()
    fts.add("dprr", "example", "consul office holding")

    results = hybrid_search(
        query="consul",
        query_vector=None,
        search_index=fts,
        vector_index=None,
        k=5,
    )
    assert len(results) >= 1
    assert results[0]["text"] == "consul office holding"
    fts.close()


def test_hybrid_vector_only_results():
    """Documents only found by vector search (no keyword overlap) still appear."""
    fts = SearchIndex()
    vec = VectorIndex()

    # Doc 1: about grain supply (no keyword overlap with "food administration")
    id1 = fts.add("dprr", "example", "praefectus annonae grain supply curator")
    # Doc 2: keyword match
    id2 = fts.add("dprr", "example", "food administration and distribution")

    v1 = _make_vector(1.0)
    v2 = _make_vector(2.0)
    vec.add_batch([id1, id2], [v1, v2])

    # Query with vector close to doc 1 but keywords matching doc 2
    results = hybrid_search(
        query="food administration",
        query_vector=v1,  # close to doc 1
        search_index=fts,
        vector_index=vec,
        k=5,
    )
    # Both docs should appear — doc 1 via vector, doc 2 via BM25
    result_texts = [r["text"] for r in results]
    assert "praefectus annonae grain supply curator" in result_texts
    assert "food administration and distribution" in result_texts

    fts.close()
    vec.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_search.py::test_hybrid_rrf_combines_results -v`
Expected: FAIL — `ImportError: cannot import name 'hybrid_search'`

- [ ] **Step 3: Implement hybrid_search**

Add to the bottom of `packages/linked-past/linked_past/core/search.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from linked_past.core.vector import VectorIndex


def hybrid_search(
    query: str,
    query_vector: list[float] | None,
    search_index: SearchIndex,
    vector_index: "VectorIndex | None",
    k: int = 10,
    dataset: str | None = None,
    doc_type: str | None = None,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """Combine BM25 and vector search via Reciprocal Rank Fusion.

    RRF score: sum(1 / (rrf_k + rank)) across both result lists.
    Falls back to FTS5-only when vector_index or query_vector is None.
    """
    # BM25 results — fetch more than k to give RRF room to rerank
    fetch_k = k * 3
    bm25_results = search_index.search(query, k=fetch_k, dataset=dataset, doc_type=doc_type)

    # Build rowid lookup for BM25 results
    bm25_by_text: dict[str, int] = {}
    bm25_docs: dict[str, dict] = {}
    for rank, result in enumerate(bm25_results):
        bm25_by_text[result["text"]] = rank
        bm25_docs[result["text"]] = result

    if vector_index is None or query_vector is None:
        return bm25_results[:k]

    # Vector results
    vec_results = vector_index.search(query_vector, k=fetch_k)

    # Map vec doc_ids back to document metadata via the FTS index's DB
    vec_docs: dict[str, int] = {}
    for rank, (doc_id, _distance) in enumerate(vec_results):
        row = search_index._conn.execute(
            "SELECT dataset, doc_type, text FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if row is None:
            continue
        text = row[2]
        # Apply same filters as BM25
        if dataset and row[0] != dataset:
            continue
        if doc_type and row[1] != doc_type:
            continue
        if text not in vec_docs:
            vec_docs[text] = rank
            if text not in bm25_docs:
                bm25_docs[text] = {"dataset": row[0], "doc_type": row[1], "text": text, "score": 0.0}

    # RRF scoring
    scored: dict[str, float] = {}
    all_texts = set(bm25_by_text.keys()) | set(vec_docs.keys())
    for text in all_texts:
        score = 0.0
        if text in bm25_by_text:
            score += 1.0 / (rrf_k + bm25_by_text[text])
        if text in vec_docs:
            score += 1.0 / (rrf_k + vec_docs[text])
        scored[text] = score

    # Sort by RRF score descending, return top k
    ranked = sorted(scored.keys(), key=lambda t: scored[t], reverse=True)[:k]
    return [{**bm25_docs[text], "score": scored[text]} for text in ranked]
```

Note: The `from __future__ import annotations` import is already at the top of `search.py`. Add the `TYPE_CHECKING` import near the top of the file, and the `hybrid_search` function at the bottom after the `SearchIndex` class.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_search.py -v`
Expected: all tests PASS (existing BM25 tests unchanged, 3 new hybrid tests pass)

- [ ] **Step 5: Run full test suite for regressions**

Run: `uv run pytest`
Expected: all existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add packages/linked-past/linked_past/core/search.py packages/linked-past/tests/test_search.py
git commit -m "feat: add hybrid_search combining BM25 + vector via RRF"
```

---

### Task 4: Embedding helper module

**Files:**
- Create: `packages/linked-past/linked_past/core/embed.py`
- Create: `packages/linked-past/tests/test_embed.py`

This module wraps FastEmbed with lazy loading so the model is only instantiated when actually needed (never in tests).

- [ ] **Step 1: Write failing test**

Create `packages/linked-past/tests/test_embed.py`:

```python
"""Tests for the embedding helper. Does NOT load the actual model — tests the interface only."""

from unittest.mock import MagicMock, patch

from linked_past.core.embed import Embedder, EMBED_MODEL, VECTOR_DIM


def test_embedder_lazy_init():
    """Model is not loaded until embed() is called."""
    embedder = Embedder()
    assert embedder._model is None


def test_embed_calls_model():
    """embed() delegates to the FastEmbed model and returns list of lists."""
    embedder = Embedder()
    fake_vectors = [[0.1] * VECTOR_DIM, [0.2] * VECTOR_DIM]

    with patch("linked_past.core.embed.TextEmbedding") as mock_cls:
        mock_model = MagicMock()
        mock_model.embed.return_value = iter(fake_vectors)
        mock_cls.return_value = mock_model

        result = embedder.embed(["hello", "world"])

    assert len(result) == 2
    assert len(result[0]) == VECTOR_DIM
    mock_cls.assert_called_once_with(model_name=EMBED_MODEL)


def test_embed_single():
    """embed_single() returns a single vector."""
    embedder = Embedder()
    fake_vector = [0.1] * VECTOR_DIM

    with patch("linked_past.core.embed.TextEmbedding") as mock_cls:
        mock_model = MagicMock()
        mock_model.embed.return_value = iter([fake_vector])
        mock_cls.return_value = mock_model

        result = embedder.embed_single("hello")

    assert len(result) == VECTOR_DIM
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_embed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'linked_past.core.embed'`

- [ ] **Step 3: Implement Embedder**

Create `packages/linked-past/linked_past/core/embed.py`:

```python
"""Lazy-loaded text embedding via FastEmbed."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

EMBED_MODEL = "intfloat/multilingual-e5-small"
VECTOR_DIM = 384


class Embedder:
    """Wraps FastEmbed TextEmbedding with lazy model loading."""

    def __init__(self) -> None:
        self._model = None

    def _load(self):
        if self._model is None:
            from fastembed import TextEmbedding

            logger.info("Loading embedding model %s...", EMBED_MODEL)
            self._model = TextEmbedding(model_name=EMBED_MODEL)
            logger.info("Embedding model loaded")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of float vectors."""
        self._load()
        return [vec.tolist() for vec in self._model.embed(texts)]

    def embed_single(self, text: str) -> list[float]:
        """Embed a single text. Returns one float vector."""
        return self.embed([text])[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_embed.py -v`
Expected: all 3 tests PASS (model is mocked, never actually loads)

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/embed.py packages/linked-past/tests/test_embed.py
git commit -m "feat: add Embedder wrapper with lazy FastEmbed loading"
```

---

### Task 5: Wire vector index into search build pipeline

**Files:**
- Modify: `packages/linked-past/linked_past/core/server.py:208-265`

- [ ] **Step 1: Update `_dataset_fingerprint` to include schema version**

In `packages/linked-past/linked_past/core/server.py`, modify `_dataset_fingerprint` (line 208):

```python
def _dataset_fingerprint(registry: DatasetRegistry) -> str:
    """Compute a fingerprint of initialized datasets + their versions.

    Changes when datasets are added, removed, or updated.
    """
    import hashlib

    parts = ["v2-hybrid"]  # Bump when index schema changes
    for name in sorted(registry.list_datasets()):
        meta = registry.get_metadata(name)
        version = meta.get("version", "unknown") if meta else "uninitialized"
        triples = meta.get("triples", 0) if meta else 0
        parts.append(f"{name}:{version}:{triples}")
    return hashlib.md5("|".join(parts).encode()).hexdigest()
```

- [ ] **Step 2: Update `_build_search_index` to build vector index**

In `packages/linked-past/linked_past/core/server.py`, modify `_build_search_index` (line 224) to return both indexes. Change the function signature and add vector building after FTS5:

```python
from linked_past.core.vector import VectorIndex


def _build_search_index(registry: DatasetRegistry, data_dir: Path) -> tuple[SearchIndex | None, VectorIndex | None]:
    """Build or reuse cached full-text and vector search indexes.

    Computes a fingerprint of initialized datasets. If the cached index
    matches, reuses it (instant startup). Otherwise rebuilds from scratch.
    """
    try:
        search_path = data_dir / "search.db"
        vec_path = data_dir / "vec.db"
        fingerprint_path = data_dir / "search.fingerprint"
        current_fp = _dataset_fingerprint(registry)

        # Check if cached index is still valid
        if search_path.exists() and fingerprint_path.exists() and vec_path.exists():
            cached_fp = fingerprint_path.read_text().strip()
            if cached_fp == current_fp:
                logger.info("Search index cache valid (fingerprint %s), reusing", current_fp[:8])
                return SearchIndex(search_path), VectorIndex(db_path=vec_path)
            logger.info("Search index stale (cached %s, current %s), rebuilding", cached_fp[:8], current_fp[:8])

        # Remove stale DB + WAL/SHM lock files from previous runs
        for db in (search_path, vec_path):
            for suffix in ("", "-wal", "-shm"):
                p = db.parent / (db.name + suffix)
                if p.exists():
                    p.unlink()

        search = SearchIndex(search_path)

        logger.info("Building search index...")
        for name in registry.list_datasets():
            plugin = registry.get_plugin(name)
            try:
                store = registry.get_store(name)
            except KeyError:
                store = None
            _index_dataset(search, name, plugin, store, registry=registry)

        # Build vector index over embeddable doc types
        vec_index = None
        embeddable_types = ("dataset", "example", "tip", "schema_comment", "shex_shape", "skos_vocab", "skos_concept")
        try:
            rows = search._conn.execute(
                "SELECT id, text FROM documents WHERE doc_type IN ({})".format(
                    ",".join("?" for _ in embeddable_types)
                ),
                embeddable_types,
            ).fetchall()

            if rows:
                from linked_past.core.embed import Embedder

                embedder = Embedder()
                doc_ids = [r[0] for r in rows]
                texts = [r[1] for r in rows]
                logger.info("Embedding %d documents...", len(texts))
                vectors = embedder.embed(texts)
                vec_index = VectorIndex(db_path=vec_path)
                vec_index.add_batch(doc_ids, vectors)
                logger.info("Vector index built (%d vectors)", len(vectors))
        except Exception as e:
            logger.warning("Failed to build vector index: %s", e)

        # Save fingerprint for next startup
        fingerprint_path.write_text(current_fp)
        logger.info("Search index built and cached (fingerprint %s)", current_fp[:8])
        return search, vec_index
    except Exception as e:
        logger.warning("Failed to build search index: %s", e)
        return None, None
```

- [ ] **Step 3: Update `build_app_context` to unpack the tuple**

In `packages/linked-past/linked_past/core/server.py`, update line 316:

Change:
```python
search_index = None if skip_search else _build_search_index(registry, data_dir)
```

To:
```python
if skip_search:
    search_index, vec_index = None, None
else:
    search_index, vec_index = _build_search_index(registry, data_dir)
```

- [ ] **Step 4: Add `vector` field to `AppContext`**

In `packages/linked-past/linked_past/core/server.py`, update the `AppContext` dataclass (line 29):

```python
@dataclass
class AppContext:
    registry: DatasetRegistry
    linkage: LinkageGraph | None = None
    search: SearchIndex | None = None
    vector: object = None  # VectorIndex | None
    embedder: object = None  # Embedder | None
    meta: object = None  # MetaEntityIndex
    session_log: list = None
    viewer: object = None  # ViewerManager | None

    def __post_init__(self):
        if self.session_log is None:
            self.session_log = []
```

- [ ] **Step 5: Pass vec_index into AppContext**

In `build_app_context`, update the return statement (line 361):

Change:
```python
return AppContext(registry=registry, linkage=linkage, search=search_index, meta=meta)
```

To:
```python
return AppContext(registry=registry, linkage=linkage, search=search_index, vector=vec_index, embedder=None, meta=meta)
```

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest`
Expected: all tests pass. Tests use `skip_search=True` so the embedding model never loads.

- [ ] **Step 7: Commit**

```bash
git add packages/linked-past/linked_past/core/server.py
git commit -m "feat: build vector index alongside FTS5 in search pipeline"
```

---

### Task 6: Wire hybrid search into `discover_datasets` with cached Embedder

**Files:**
- Modify: `packages/linked-past/linked_past/core/server.py:29-36, 361, 666-706`

- [ ] **Step 1: Add embedder field to AppContext**

In `packages/linked-past/linked_past/core/server.py`, update the `AppContext` dataclass (line 29):

```python
@dataclass
class AppContext:
    registry: DatasetRegistry
    linkage: LinkageGraph | None = None
    search: SearchIndex | None = None
    vector: object = None  # VectorIndex | None
    embedder: object = None  # Embedder | None
    meta: object = None  # MetaEntityIndex
    session_log: list = None
    viewer: object = None  # ViewerManager | None

    def __post_init__(self):
        if self.session_log is None:
            self.session_log = []
```

- [ ] **Step 2: Create Embedder in build_app_context when vector index exists**

In `build_app_context`, after the vector index is built but before the return, add:

```python
    embedder = None
    if vec_index is not None:
        try:
            from linked_past.core.embed import Embedder
            embedder = Embedder()
        except Exception as e:
            logger.warning("Failed to create embedder: %s", e)
```

Update the return statement:
```python
    return AppContext(registry=registry, linkage=linkage, search=search_index, vector=vec_index, embedder=embedder, meta=meta)
```

- [ ] **Step 3: Update `discover_datasets` to use hybrid search with cached embedder**

In `packages/linked-past/linked_past/core/server.py`, modify the `discover_datasets` tool (line 666):

Change:
```python
        if topic and app.search:
            results = app.search.search(topic, k=10)
            relevant_datasets = {r["dataset"] for r in results}
        else:
            relevant_datasets = None
```

To:
```python
        if topic and app.search:
            from linked_past.core.search import hybrid_search

            query_vector = None
            if app.vector and app.embedder:
                try:
                    query_vector = app.embedder.embed_single(topic)
                except Exception:
                    logger.debug("Vector embedding failed for topic query, using BM25 only")

            results = hybrid_search(
                query=topic,
                query_vector=query_vector,
                search_index=app.search,
                vector_index=app.vector,
                k=10,
            )
            relevant_datasets = {r["dataset"] for r in results}
        else:
            relevant_datasets = None
```

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest`
Expected: all tests pass. Integration tests use `skip_search=True`, so `app.search` is None and the hybrid path is never hit.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/server.py
git commit -m "feat: use hybrid search in discover_datasets with cached Embedder"
```

---

### Task 7: Integration smoke test

**Files:**
- Modify: `packages/linked-past/tests/test_search.py`

Add one test that exercises the full hybrid path through `SearchIndex` + `VectorIndex` together, using fixture vectors (no embedding model).

- [ ] **Step 1: Write the integration test**

Append to `packages/linked-past/tests/test_search.py`:

```python
def test_hybrid_search_with_dataset_filter():
    """Hybrid search respects dataset filter."""
    fts = SearchIndex()
    vec = VectorIndex()

    id1 = fts.add("dprr", "example", "consul office holding")
    id2 = fts.add("pleiades", "example", "ancient place geography")

    v1 = _make_vector(1.0)
    v2 = _make_vector(2.0)
    vec.add_batch([id1, id2], [v1, v2])

    results = hybrid_search(
        query="consul",
        query_vector=v1,
        search_index=fts,
        vector_index=vec,
        k=5,
        dataset="dprr",
    )
    assert all(r["dataset"] == "dprr" for r in results)

    fts.close()
    vec.close()


def test_hybrid_search_with_doc_type_filter():
    """Hybrid search respects doc_type filter."""
    fts = SearchIndex()
    vec = VectorIndex()

    id1 = fts.add("dprr", "example", "consul office query")
    id2 = fts.add("dprr", "tip", "use consul for office searches")

    v1 = _make_vector(1.0)
    v2 = _make_vector(2.0)
    vec.add_batch([id1, id2], [v1, v2])

    results = hybrid_search(
        query="consul",
        query_vector=v1,
        search_index=fts,
        vector_index=vec,
        k=5,
        doc_type="example",
    )
    assert all(r["doc_type"] == "example" for r in results)

    fts.close()
    vec.close()
```

- [ ] **Step 2: Run all search tests**

Run: `uv run pytest packages/linked-past/tests/test_search.py -v`
Expected: all tests PASS

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest`
Expected: all tests pass, no regressions

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past/tests/test_search.py
git commit -m "test: add hybrid search filter integration tests"
```
