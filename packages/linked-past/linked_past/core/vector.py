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
        rows = self._conn.execute(
            "SELECT doc_id, distance FROM vec_documents "
            "WHERE embedding MATCH ? AND k = ? "
            "ORDER BY distance",
            [sqlite_vec.serialize_float32(query_vector), k],
        ).fetchall()
        return [(int(row[0]), float(row[1])) for row in rows]

    def clear(self) -> None:
        """Remove all vectors."""
        self._conn.execute("DELETE FROM vec_documents")
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
