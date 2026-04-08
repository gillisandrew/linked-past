# Semantic Example Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace rigid class-name example matching in `validate_sparql` with hybrid search (BM25 + vector similarity) using the existing search infrastructure.

**Architecture:** Two changes: (1) add a `get_relevant_tips()` method to `DatasetPlugin` that extracts just the tips half of the current `get_relevant_context()`, (2) update `validate_sparql` to use `hybrid_search()` for examples when the search index is available, falling back to class matching otherwise.

**Tech Stack:** Python, SQLite FTS5, sqlite-vec, FastEmbed (all already integrated)

**Spec:** `docs/superpowers/specs/2026-04-08-semantic-example-search-design.md`

---

### Task 1: Add `get_relevant_tips` to DatasetPlugin

**Files:**
- Modify: `packages/linked-past/linked_past/datasets/base.py`
- Test: `packages/linked-past/tests/test_base_plugin.py`

Currently `get_relevant_context()` (base.py:178-200) returns both tips AND examples as a combined markdown string. We need a tips-only method so `validate_sparql` can source examples from hybrid search while keeping tips class-matched.

- [ ] **Step 1: Write the failing test**

Create `packages/linked-past/tests/test_base_plugin.py`:

```python
"""Tests for DatasetPlugin context retrieval methods."""

from unittest.mock import MagicMock, patch
from linked_past.datasets.base import DatasetPlugin


class FakePlugin(DatasetPlugin):
    """Minimal concrete plugin for testing."""

    name = "test"
    oci_ref = "ghcr.io/test:latest"

    def fetch(self) -> bytes:
        return b""


@patch("linked_past.datasets.base.DatasetPlugin.__init__", return_value=None)
def test_get_relevant_tips_returns_tips_only(mock_init):
    plugin = FakePlugin.__new__(FakePlugin)
    plugin._tips = [
        {"title": "Tip about Person", "body": "Use dprr:hasPersonName", "classes": ["Person"]},
        {"title": "General tip", "body": "Always use LIMIT", "classes": []},
        {"title": "Tip about Office", "body": "Use PostAssertion", "classes": ["PostAssertion"]},
    ]
    plugin._schema_dict = {"Person": {}, "PostAssertion": {}}
    plugin._examples = []

    # Query mentioning Person class
    sparql = "SELECT ?p WHERE { ?p a dprr:Person }"
    result = plugin.get_relevant_tips(sparql)

    assert "Tip about Person" in result
    assert "Tip about Office" not in result
    # Should NOT contain any example queries
    assert "```sparql" not in result


@patch("linked_past.datasets.base.DatasetPlugin.__init__", return_value=None)
def test_get_relevant_tips_returns_empty_when_no_classes(mock_init):
    plugin = FakePlugin.__new__(FakePlugin)
    plugin._tips = [
        {"title": "Tip", "body": "body", "classes": ["Person"]},
    ]
    plugin._schema_dict = {}
    plugin._examples = []

    sparql = "SELECT ?x WHERE { ?x ?p ?o }"
    result = plugin.get_relevant_tips(sparql)

    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_base_plugin.py -v`
Expected: FAIL with `AttributeError: 'FakePlugin' object has no attribute 'get_relevant_tips'`

- [ ] **Step 3: Implement `get_relevant_tips`**

In `base.py`, add a new method after `get_relevant_context()` (after line 200):

```python
def get_relevant_tips(self, sparql: str) -> str:
    """Return class-matched tips for a SPARQL query (no examples)."""
    from linked_past.core.context import get_relevant_tips, render_tips
    from linked_past.core.validate import extract_query_classes

    classes = extract_query_classes(sparql, self._schema_dict)
    if not classes:
        return ""
    tips = get_relevant_tips(self._tips, classes)
    if not tips:
        return ""
    return f"\n\n---\n\n## Relevant Tips\n\n{render_tips(tips)}"
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/linked-past/tests/test_base_plugin.py -v`
Expected: PASS (both tests)

Run: `uv run pytest -q`
Expected: All existing tests pass (no regressions).

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/datasets/base.py packages/linked-past/tests/test_base_plugin.py
git commit -m "feat: add get_relevant_tips method to DatasetPlugin"
```

---

### Task 2: Wire hybrid search into `validate_sparql`

**Files:**
- Modify: `packages/linked-past/linked_past/core/server.py`
- Test: `packages/linked-past/tests/test_validate_sparql_examples.py`

Replace the two `plugin.get_relevant_context()` calls in `validate_sparql` (lines 812 and 833) with hybrid search for examples + class-matched tips.

- [ ] **Step 1: Write the failing test**

Create `packages/linked-past/tests/test_validate_sparql_examples.py`:

```python
"""Tests for hybrid example search in validate_sparql."""

import pytest
from unittest.mock import MagicMock, patch

from linked_past.core.server import _get_example_context


def test_get_example_context_uses_hybrid_search():
    """When search index is available, uses hybrid_search for examples."""
    search_index = MagicMock()
    vector_index = MagicMock()
    embedder = MagicMock()
    embedder.embed_single.return_value = [0.1] * 384

    # Mock hybrid_search to return one example result
    with patch("linked_past.core.server.hybrid_search") as mock_hs:
        mock_hs.return_value = [
            {"dataset": "dprr", "doc_type": "example", "text": "List all consuls\nSELECT ?p WHERE { ?p a dprr:Person }"},
        ]
        result = _get_example_context(
            sparql="SELECT ?p WHERE { ?p a dprr:Person }",
            dataset="dprr",
            search_index=search_index,
            vector_index=vector_index,
            embedder=embedder,
        )

    assert "List all consuls" in result
    mock_hs.assert_called_once()
    call_kwargs = mock_hs.call_args
    assert call_kwargs.kwargs["dataset"] == "dprr"
    assert call_kwargs.kwargs["doc_type"] == "example"
    assert call_kwargs.kwargs["k"] == 3


def test_get_example_context_returns_empty_when_no_results():
    """When hybrid search finds nothing, returns empty string."""
    search_index = MagicMock()
    embedder = MagicMock()
    embedder.embed_single.return_value = [0.1] * 384

    with patch("linked_past.core.server.hybrid_search") as mock_hs:
        mock_hs.return_value = []
        result = _get_example_context(
            sparql="SELECT ?x WHERE { ?x ?p ?o }",
            dataset="dprr",
            search_index=search_index,
            vector_index=None,
            embedder=embedder,
        )

    assert result == ""


def test_get_example_context_returns_empty_when_no_search_index():
    """When search index is None, returns empty string."""
    result = _get_example_context(
        sparql="SELECT ?x WHERE { ?x ?p ?o }",
        dataset="dprr",
        search_index=None,
        vector_index=None,
        embedder=None,
    )
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_validate_sparql_examples.py -v`
Expected: FAIL with `ImportError: cannot import name '_get_example_context'`

- [ ] **Step 3: Add `_get_example_context` helper**

In `server.py`, add a new helper function before the `create_mcp_server` function. This encapsulates the hybrid search → markdown rendering for examples:

```python
def _get_example_context(
    sparql: str,
    dataset: str,
    search_index,
    vector_index,
    embedder,
) -> str:
    """Search for relevant example queries using hybrid search.

    Returns formatted markdown, or empty string if no search index
    or no results.
    """
    if search_index is None:
        return ""

    from linked_past.core.search import hybrid_search

    query_vector = None
    if vector_index and embedder:
        try:
            query_vector = embedder.embed_single(sparql)
        except Exception:
            logger.debug("Vector embedding failed for example search, using BM25 only")

    results = hybrid_search(
        query=sparql,
        query_vector=query_vector,
        search_index=search_index,
        vector_index=vector_index,
        k=3,
        dataset=dataset,
        doc_type="example",
    )

    if not results:
        return ""

    # Each result's text is "question\nsparql" as indexed by _index_dataset
    sections = []
    for r in results:
        text = r["text"]
        # Split into question (first line) and sparql (rest)
        lines = text.split("\n", 1)
        question = lines[0]
        sparql_text = lines[1] if len(lines) > 1 else ""
        sections.append(f"Question: {question}\n\n```sparql\n{sparql_text.strip()}\n```")

    return f"\n\n---\n\n## Relevant Examples\n\n" + "\n\n---\n\n".join(sections)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/linked-past/tests/test_validate_sparql_examples.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Update `validate_sparql` to use the new helper**

In `server.py`, replace the two `plugin.get_relevant_context()` calls in `validate_sparql` (lines 812 and 833).

Current line 812:
```python
return base + plugin.get_relevant_context(sparql)
```

Replace with:
```python
if app.search:
    return base + _get_example_context(sparql, dataset, app.search, app.vector, app.embedder) + plugin.get_relevant_tips(sparql)
return base + plugin.get_relevant_context(sparql)
```

Current line 833:
```python
return base + plugin.get_relevant_context(fixed_sparql)
```

Replace with:
```python
if app.search:
    return base + _get_example_context(fixed_sparql, dataset, app.search, app.vector, app.embedder) + plugin.get_relevant_tips(fixed_sparql)
return base + plugin.get_relevant_context(fixed_sparql)
```

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest -q`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add packages/linked-past/linked_past/core/server.py packages/linked-past/tests/test_validate_sparql_examples.py
git commit -m "feat: semantic example search in validate_sparql via hybrid search"
```
