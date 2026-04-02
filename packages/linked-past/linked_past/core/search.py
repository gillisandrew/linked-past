"""SQLite FTS5-backed full-text search index."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
        logger.debug("indexed %d documents dataset=%s", len(rows), rows[0][0] if rows else "?")
        return len(rows)

    def build(self) -> int:
        """No-op for API compatibility. FTS5 indexes on insert."""
        return 0

    def search(
        self,
        query: str,
        k: int = 5,
        dataset: str | None = None,
        doc_type: str | None = None,
        operator: str = "OR",
    ) -> list[dict[str, Any]]:
        """Full-text search with BM25 ranking. Returns top-k results.

        Uses porter stemming and unicode tokenization.
        Each query term gets prefix matching (e.g. "consul" matches "consular").

        Args:
            operator: "OR" for broad recall, "AND" for precision (all terms must match).
            doc_type: Filter by document type (e.g., "entity_label").
        """
        if not query or not query.strip():
            return []

        terms = query.strip().split()
        fts_query = f" {operator} ".join(f'"{t}"*' for t in terms if t)

        try:
            where = ["documents_fts MATCH ?"]
            params: list = [fts_query]
            if dataset:
                where.append("d.dataset = ?")
                params.append(dataset)
            if doc_type:
                where.append("d.doc_type = ?")
                params.append(doc_type)
            params.append(k)
            where_clause = " AND ".join(where)
            rows = self._conn.execute(
                "SELECT d.dataset, d.doc_type, d.text, "
                "       bm25(documents_fts) AS score "
                "FROM documents_fts f "
                "JOIN documents d ON d.id = f.rowid "
                f"WHERE {where_clause} "
                "ORDER BY score "
                "LIMIT ?",
                params,
            ).fetchall()
        except sqlite3.OperationalError:
            # Malformed FTS query — fall back to empty results
            return []

        # BM25 returns negative scores (lower = better match), negate for consistency
        results = [
            {"dataset": ds, "doc_type": dt, "text": text, "score": -score}
            for ds, dt, text, score in rows
        ]
        logger.debug("search query=%r dataset=%s results=%d", query, dataset, len(results))
        return results

    def clear_dataset(self, dataset: str) -> int:
        """Remove all documents for a dataset. Returns count removed."""
        cursor = self._conn.execute(
            "DELETE FROM documents WHERE dataset = ?", (dataset,)
        )
        self._conn.commit()
        logger.info("cleared search index dataset=%s count=%d", dataset, cursor.rowcount)
        return cursor.rowcount

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
