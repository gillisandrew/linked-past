"""Tests for the FTS5 search index."""

from linked_past.core.search import SearchIndex


def test_add_and_search():
    idx = SearchIndex()
    idx.add("dprr", "dataset", "Digital Prosopography of the Roman Republic")
    idx.add("pleiades", "dataset", "Pleiades Gazetteer of Ancient Places")

    results = idx.search("Roman Republic")
    assert len(results) >= 1
    assert results[0]["dataset"] == "dprr"
    idx.close()


def test_search_by_dataset():
    idx = SearchIndex()
    idx.add("dprr", "schema", "Person: A historical person from the Roman Republic")
    idx.add("pleiades", "schema", "Place: An ancient geographic place")

    results = idx.search("person", dataset="dprr")
    assert len(results) >= 1
    assert all(r["dataset"] == "dprr" for r in results)

    results = idx.search("person", dataset="pleiades")
    assert len(results) == 0
    idx.close()


def test_persistence(tmp_path):
    db_path = tmp_path / "search.db"
    idx = SearchIndex(db_path=db_path)
    idx.add("dprr", "tip", "Use STRSTARTS for office name matching")
    idx.close()

    idx2 = SearchIndex(db_path=db_path)
    results = idx2.search("office matching")
    assert len(results) >= 1
    idx2.close()


def test_clear_dataset():
    idx = SearchIndex()
    idx.add("dprr", "schema", "Person class")
    idx.add("pleiades", "schema", "Place class")

    removed = idx.clear_dataset("dprr")
    assert removed == 1

    results = idx.search("Person")
    assert len(results) == 0

    results = idx.search("Place")
    assert len(results) == 1
    idx.close()


def test_empty_search():
    idx = SearchIndex()
    results = idx.search("")
    assert results == []
    results = idx.search("nonexistent term xyz")
    assert results == []
    idx.close()


def test_prefix_matching():
    idx = SearchIndex()
    idx.add("dprr", "schema", "PostAssertion: an assertion about a consular office")

    # "consul" should match "consular" via prefix
    results = idx.search("consul")
    assert len(results) >= 1
    idx.close()


def test_porter_stemming():
    idx = SearchIndex()
    idx.add("dprr", "schema", "Assertions about office holdings in the Republic")

    # "assertion" should match "assertions" via stemming
    results = idx.search("assertion")
    assert len(results) >= 1
    idx.close()


def test_bm25_ranking():
    idx = SearchIndex()
    idx.add("dprr", "schema", "Person: A historical person from the Roman Republic period")
    idx.add("dprr", "tip", "The word person appears once here")
    idx.add("dprr", "example", "No relevant content at all about places")

    results = idx.search("person Roman Republic", k=3)
    # The schema doc mentions all three terms, should rank highest
    assert results[0]["doc_type"] == "schema"
    idx.close()


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
