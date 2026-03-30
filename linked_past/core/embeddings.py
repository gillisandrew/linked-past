"""SQLite-backed embedding index using fastembed for semantic search."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import numpy as np


def _array_to_blob(arr: np.ndarray) -> bytes:
    return arr.astype(np.float32).tobytes()


def _blob_to_array(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


class EmbeddingIndex:
    """Manages document embeddings in SQLite for brute-force cosine similarity search."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        model_name: str = "BAAI/bge-small-en-v1.5",
    ) -> None:
        self._model_name = model_name
        self._model: Any = None  # lazy-loaded

        if db_path is None:
            self._conn = sqlite3.connect(":memory:")
        else:
            self._conn = sqlite3.connect(str(db_path))

        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding BLOB
            )"""
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )"""
        )
        self._conn.commit()

    def _get_model(self) -> Any:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self._model_name)
        return self._model

    def add(self, dataset: str, doc_type: str, text: str) -> int:
        """Insert a document. Returns the row id. Embedding is NULL until build()."""
        cursor = self._conn.execute(
            "INSERT INTO documents (dataset, doc_type, text) VALUES (?, ?, ?)",
            (dataset, doc_type, text),
        )
        self._conn.commit()
        return cursor.lastrowid

    def build(self) -> int:
        """Compute embeddings for all documents with NULL embedding. Returns count built."""
        rows = self._conn.execute(
            "SELECT id, text FROM documents WHERE embedding IS NULL"
        ).fetchall()
        if not rows:
            return 0

        ids = [r[0] for r in rows]
        texts = [r[1] for r in rows]
        model = self._get_model()
        embeddings = list(model.embed(texts))

        for row_id, emb in zip(ids, embeddings):
            blob = _array_to_blob(np.array(emb))
            self._conn.execute(
                "UPDATE documents SET embedding = ? WHERE id = ?",
                (blob, row_id),
            )
        self._conn.commit()
        return len(ids)

    def search(
        self,
        query: str,
        k: int = 5,
        dataset: str | None = None,
    ) -> list[dict[str, Any]]:
        """Brute-force cosine similarity search. Returns top-k results."""
        model = self._get_model()
        query_emb = np.array(list(model.embed([query]))[0], dtype=np.float32)
        query_norm = np.linalg.norm(query_emb)
        if query_norm == 0:
            return []

        sql = "SELECT id, dataset, doc_type, text, embedding FROM documents WHERE embedding IS NOT NULL"
        if dataset:
            rows = self._conn.execute(sql + " AND dataset = ?", (dataset,)).fetchall()
        else:
            rows = self._conn.execute(sql).fetchall()

        scored = []
        for row_id, ds, dt, text, blob in rows:
            emb = _blob_to_array(blob)
            emb_norm = np.linalg.norm(emb)
            if emb_norm == 0:
                continue
            score = float(np.dot(query_emb, emb) / (query_norm * emb_norm))
            scored.append({"dataset": ds, "doc_type": dt, "text": text, "score": score})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    def clear_dataset(self, dataset: str) -> int:
        """Remove all documents for a dataset. Returns count removed."""
        cursor = self._conn.execute(
            "DELETE FROM documents WHERE dataset = ?", (dataset,)
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
