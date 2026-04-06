"""Tests for the sqlite-vec vector index. Uses pre-computed fixture vectors — no embedding model."""

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
