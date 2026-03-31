"""Tests for multi-document embedding strategy in _build_embeddings."""

from linked_past.core.embeddings import EmbeddingIndex


def test_schema_class_produces_multiple_documents():
    """Each schema class should produce separate documents for label+URI and comment."""
    index = EmbeddingIndex()  # in-memory

    cls_name = "Person"
    cls_data = {
        "comment": "A historical person from the Roman Republic period.",
        "uri": "vocab:Person",
        "label": "Person",
    }

    # Label + URI document
    index.add("dprr", "schema_label", f"{cls_data.get('label', cls_name)} ({cls_data['uri']})")
    # Comment document
    index.add("dprr", "schema_comment", f"{cls_name}: {cls_data['comment']}")

    rows = index._conn.execute("SELECT doc_type, text FROM documents ORDER BY id").fetchall()
    assert len(rows) == 2
    assert rows[0][0] == "schema_label"
    assert "Person" in rows[0][1]
    assert "vocab:Person" in rows[0][1]
    assert rows[1][0] == "schema_comment"
    assert "historical person" in rows[1][1]
    index.close()


def test_example_queries_embedded_per_class():
    """Example queries mentioning a class should be embedded as separate documents."""
    index = EmbeddingIndex()

    examples = [
        {"question": "Who held the office of consul?", "sparql": "SELECT ?p WHERE { ?p a vocab:Person }"},
        {"question": "List all offices", "sparql": "SELECT ?o WHERE { ?o a vocab:Office }"},
    ]

    for ex in examples:
        index.add("dprr", "example", f"{ex['question']}\n{ex['sparql']}")

    count = index._conn.execute("SELECT COUNT(*) FROM documents WHERE doc_type = 'example'").fetchone()[0]
    assert count == 2
    index.close()
