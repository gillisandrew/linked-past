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
