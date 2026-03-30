"""Tests for the embedding index."""

import tempfile
from pathlib import Path

import pytest

from linked_past.core.embeddings import EmbeddingIndex


@pytest.fixture
def index():
    idx = EmbeddingIndex()
    idx.add("dprr", "person", "Marcus Tullius Cicero was a Roman statesman and orator")
    idx.add("dprr", "person", "Gaius Julius Caesar was a Roman general and dictator")
    idx.add("pleiades", "place", "Rome was the capital of the Roman Republic and Empire")
    idx.add("periodo", "period", "The Late Roman Republic period from 133 to 31 BC")
    idx.add("nomisma", "coin", "Denarius silver coin minted during the Roman Republic")
    idx.build()
    return idx


def test_add_and_search(index):
    results = index.search("Roman politician and speaker", k=3)
    assert len(results) == 3
    # Cicero (statesman/orator) should be most relevant to "politician and speaker"
    texts = [r["text"] for r in results]
    assert any("Cicero" in t for t in texts)
    # All scores should be between 0 and 1
    for r in results:
        assert 0 <= r["score"] <= 1.0


def test_search_by_dataset(index):
    results = index.search("Roman city", k=5, dataset="pleiades")
    assert len(results) == 1
    assert results[0]["dataset"] == "pleiades"


def test_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        idx = EmbeddingIndex(db_path=db_path)
        idx.add("dprr", "person", "Cicero the orator")
        idx.build()
        idx.close()

        idx2 = EmbeddingIndex(db_path=db_path)
        results = idx2.search("Roman speaker", k=1)
        assert len(results) == 1
        assert "Cicero" in results[0]["text"]
        idx2.close()


def test_clear_dataset(index):
    removed = index.clear_dataset("pleiades")
    assert removed == 1
    results = index.search("Rome city", k=5, dataset="pleiades")
    assert len(results) == 0


def test_empty_search():
    idx = EmbeddingIndex()
    results = idx.search("anything", k=5)
    assert results == []
    idx.close()
