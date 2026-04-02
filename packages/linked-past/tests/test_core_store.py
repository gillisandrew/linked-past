# tests/test_core_store.py
from pathlib import Path

import pytest
from linked_past.core.store import (
    create_store,
    execute_ask,
    execute_query,
    get_data_dir,
    get_read_only_store,
    is_initialized,
    load_rdf,
    materialize,
)

SAMPLE_TURTLE = """\
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/> .

ex:Thing1 a ex:Widget ;
    rdfs:label "Widget One" .
ex:Thing2 a ex:Widget ;
    rdfs:label "Widget Two" .
"""


def test_get_data_dir_default(monkeypatch):
    monkeypatch.delenv("LINKED_PAST_DATA_DIR", raising=False)
    monkeypatch.delenv("DPRR_DATA_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    result = get_data_dir()
    assert result == Path.home() / ".local" / "share" / "linked-past"


def test_get_data_dir_linked_past_env(monkeypatch):
    monkeypatch.setenv("LINKED_PAST_DATA_DIR", "/tmp/lp")
    result = get_data_dir()
    assert result == Path("/tmp/lp")


def test_get_data_dir_xdg(monkeypatch):
    monkeypatch.delenv("LINKED_PAST_DATA_DIR", raising=False)
    monkeypatch.delenv("DPRR_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdg")
    result = get_data_dir()
    assert result == Path("/tmp/xdg/linked-past")


def test_create_and_load(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    count = load_rdf(store, ttl)
    assert count > 0


def test_is_initialized_false(tmp_path):
    assert not is_initialized(tmp_path / "nonexistent")


def test_is_initialized_true(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    del store
    assert is_initialized(store_path)


def test_read_only_store(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    del store
    ro = get_read_only_store(store_path)
    results = execute_query(ro, "SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }")
    assert int(results[0]["c"]) > 0


def test_execute_query_select(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    results = execute_query(
        store,
        'PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n'
        'SELECT ?s ?label WHERE { ?s rdfs:label ?label } ORDER BY ?label',
    )
    assert len(results) == 2
    assert results[0]["label"] == "Widget One"


def test_execute_query_non_select_raises(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    with pytest.raises(ValueError, match="Only SELECT"):
        execute_query(store, "ASK { ?s ?p ?o }")


def test_execute_ask_true(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    result = execute_ask(store, "ASK { ?s a <http://example.org/Widget> }")
    assert result is True


def test_execute_ask_false(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    result = execute_ask(store, "ASK { ?s a <http://example.org/Nonexistent> }")
    assert result is False


def test_execute_ask_rejects_select(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(SAMPLE_TURTLE)
    load_rdf(store, ttl)
    with pytest.raises(ValueError, match="Expected ASK"):
        execute_ask(store, "SELECT ?s WHERE { ?s ?p ?o }")


# ── Materialization tests ────────────────────────────────────────────


def test_materialize_subpropertyof(tmp_path):
    """rdfs:subPropertyOf materialization: hasPersonName subPropertyOf rdfs:label."""
    store = create_store(tmp_path / "store")
    ttl = tmp_path / "data.ttl"
    ttl.write_text(
        '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
        '@prefix owl: <http://www.w3.org/2002/07/owl#> .\n'
        '@prefix ex: <http://example.org/> .\n'
        '\n'
        'ex:hasPersonName a owl:DatatypeProperty ;\n'
        '    rdfs:subPropertyOf rdfs:label .\n'
        '\n'
        'ex:Person1 ex:hasPersonName "Marcus Tullius Cicero" .\n'
    )
    load_rdf(store, ttl)

    # Before materialization: no rdfs:label on Person1
    rows = list(store.query(
        'SELECT ?label WHERE { <http://example.org/Person1> <http://www.w3.org/2000/01/rdf-schema#label> ?label }'
    ))
    assert len(rows) == 0

    added = materialize(store)
    assert added > 0

    # After materialization: rdfs:label is inferred
    rows = list(store.query(
        'SELECT ?label WHERE { <http://example.org/Person1> <http://www.w3.org/2000/01/rdf-schema#label> ?label }'
    ))
    assert len(rows) == 1
    assert rows[0][0].value == "Marcus Tullius Cicero"


def test_materialize_subclassof(tmp_path):
    """rdfs:subClassOf materialization: Person subClassOf Agent."""
    store = create_store(tmp_path / "store")
    ttl = tmp_path / "data.ttl"
    ttl.write_text(
        '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
        '@prefix ex: <http://example.org/> .\n'
        '\n'
        'ex:Person rdfs:subClassOf ex:Agent .\n'
        'ex:Person1 a ex:Person .\n'
    )
    load_rdf(store, ttl)

    # Before: not typed as Agent
    result = store.query('ASK { <http://example.org/Person1> a <http://example.org/Agent> }')
    assert not bool(result)

    materialize(store)

    # After: inferred as Agent
    result = store.query('ASK { <http://example.org/Person1> a <http://example.org/Agent> }')
    assert bool(result)


def test_materialize_no_axioms(tmp_path):
    """When data has no RDFS/OWL axioms, materialize is a no-op."""
    store = create_store(tmp_path / "store")
    ttl = tmp_path / "data.ttl"
    ttl.write_text(
        '@prefix ex: <http://example.org/> .\n'
        'ex:Thing1 a ex:Widget .\n'
    )
    load_rdf(store, ttl)
    original = len(store)
    added = materialize(store)
    assert added == 0
    assert len(store) == original


def test_materialize_idempotent(tmp_path):
    """Running materialize twice doesn't add duplicate triples."""
    store = create_store(tmp_path / "store")
    ttl = tmp_path / "data.ttl"
    ttl.write_text(
        '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
        '@prefix ex: <http://example.org/> .\n'
        'ex:Person rdfs:subClassOf ex:Agent .\n'
        'ex:Person1 a ex:Person .\n'
    )
    load_rdf(store, ttl)
    materialize(store)
    count_after_first = len(store)
    second = materialize(store)
    assert second == 0
    assert len(store) == count_after_first
