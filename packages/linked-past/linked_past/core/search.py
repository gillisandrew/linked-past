"""SQLite FTS5-backed full-text search index."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class SearchIndex:
    """Full-text search over documents using SQLite FTS5 with BM25 ranking."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            self._conn = sqlite3.connect(":memory:")
        else:
            self._conn = sqlite3.connect(str(db_path))

        self._conn.execute("PRAGMA journal_mode=WAL")

        # Main table for metadata (dataset, doc_type)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                text TEXT NOT NULL
            )"""
        )

        # FTS5 virtual table for full-text search
        self._conn.execute(
            """CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                text,
                content='documents',
                content_rowid='id',
                tokenize='porter unicode61'
            )"""
        )

        # Triggers to keep FTS in sync with documents table
        self._conn.executescript("""
            CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                INSERT INTO documents_fts(rowid, text) VALUES (new.id, new.text);
            END;
            CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                INSERT INTO documents_fts(documents_fts, rowid, text) VALUES('delete', old.id, old.text);
            END;
        """)
        self._conn.commit()

    def add(self, dataset: str, doc_type: str, text: str) -> int:
        """Insert a document. Automatically indexed by FTS5. Returns the row id."""
        cursor = self._conn.execute(
            "INSERT INTO documents (dataset, doc_type, text) VALUES (?, ?, ?)",
            (dataset, doc_type, text),
        )
        self._conn.commit()
        return cursor.lastrowid

    def add_batch(self, rows: list[tuple[str, str, str]]) -> int:
        """Insert multiple (dataset, doc_type, text) rows in a single transaction."""
        self._conn.executemany(
            "INSERT INTO documents (dataset, doc_type, text) VALUES (?, ?, ?)",
            rows,
        )
        self._conn.commit()
        return len(rows)

    def build(self) -> int:
        """No-op for API compatibility. FTS5 indexes on insert."""
        return 0

    def search(
        self,
        query: str,
        k: int = 5,
        dataset: str | None = None,
    ) -> list[dict[str, Any]]:
        """Full-text search with BM25 ranking. Returns top-k results.

        Uses porter stemming and unicode tokenization.
        Each query term gets prefix matching (e.g. "consul" matches "consular").
        """
        if not query or not query.strip():
            return []

        # Tokenize query for FTS5: prefix matching + OR for recall
        # OR ensures documents matching any term are returned; BM25 ranks
        # documents matching more terms higher.
        terms = query.strip().split()
        fts_query = " OR ".join(f'"{t}"*' for t in terms if t)

        try:
            if dataset:
                rows = self._conn.execute(
                    "SELECT d.dataset, d.doc_type, d.text, "
                    "       bm25(documents_fts) AS score "
                    "FROM documents_fts f "
                    "JOIN documents d ON d.id = f.rowid "
                    "WHERE documents_fts MATCH ? AND d.dataset = ? "
                    "ORDER BY score "
                    "LIMIT ?",
                    (fts_query, dataset, k),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT d.dataset, d.doc_type, d.text, "
                    "       bm25(documents_fts) AS score "
                    "FROM documents_fts f "
                    "JOIN documents d ON d.id = f.rowid "
                    "WHERE documents_fts MATCH ? "
                    "ORDER BY score "
                    "LIMIT ?",
                    (fts_query, k),
                ).fetchall()
        except sqlite3.OperationalError:
            # Malformed FTS query — fall back to empty results
            return []

        # BM25 returns negative scores (lower = better match), negate for consistency
        return [
            {"dataset": ds, "doc_type": dt, "text": text, "score": -score}
            for ds, dt, text, score in rows
        ]

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
