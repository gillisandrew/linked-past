"""sqlite-vec backed vector index for semantic similarity search."""

from __future__ import annotations

import logging
import sqlite3
import struct
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _serialize_float32(vector: list[float]) -> bytes:
    """Serialize a float list to little-endian float32 bytes for sqlite-vec."""
    return struct.pack(f"{len(vector)}f", *vector)


class VectorIndex:
    """384-dim float vector index backed by sqlite-vec."""

    DIM = 384

    def __init__(self, db_path: str | Path | None = None) -> None:
        import sqlite_vec

        if db_path is None:
            self._conn = sqlite3.connect(":memory:")
        else:
            self._conn = sqlite3.connect(str(db_path))

        self._conn.enable_load_extension(True)
        sqlite_vec.load(self._conn)
        self._conn.enable_load_extension(False)

        self._conn.execute(
            f"""CREATE VIRTUAL TABLE IF NOT EXISTS vec_documents
                USING vec0(
                    doc_id INTEGER PRIMARY KEY,
                    embedding float[{self.DIM}]
                )"""
        )
        self._conn.commit()

    def add_batch(self, ids: list[int], vectors: list[list[float]]) -> None:
        """Insert (doc_id, vector) pairs in bulk."""
        rows = [
            (doc_id, _serialize_float32(vec))
            for doc_id, vec in zip(ids, vectors)
        ]
        self._conn.executemany(
            "INSERT OR REPLACE INTO vec_documents(doc_id, embedding) VALUES (?, ?)",
            rows,
        )
        self._conn.commit()
        logger.debug("vector index: added %d vectors", len(rows))

    def search(self, query_vector: list[float], k: int = 10) -> list[tuple[int, float]]:
        """Return top-k (doc_id, distance) pairs sorted by ascending distance."""
        serialized = _serialize_float32(query_vector)
        rows = self._conn.execute(
            """SELECT doc_id, distance
               FROM vec_documents
               WHERE embedding MATCH ?
               AND k = ?
               ORDER BY distance""",
            (serialized, k),
        ).fetchall()
        return [(int(doc_id), float(dist)) for doc_id, dist in rows]

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
