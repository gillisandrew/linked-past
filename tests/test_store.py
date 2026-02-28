import tempfile
from pathlib import Path

import pytest

from dprr_tool.store import execute_query, get_or_create_store, is_initialized, load_rdf

SAMPLE_TURTLE = """\
@prefix vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://romanrepublic.ac.uk/rdf/entity/Person/1> a vocab:Person ;
    vocab:hasPersonName "IUNI0001 L. Iunius Brutus" ;
    vocab:hasDprrID "IUNI0001" ;
    vocab:hasID "1" ;
    vocab:hasNomen "Iunius" ;
    vocab:hasCognomen "Brutus" ;
    vocab:isSex <http://romanrepublic.ac.uk/rdf/entity/Sex/Male> ;
    vocab:hasEraFrom "-509"^^xsd:integer ;
    vocab:hasEraTo "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/Person/2> a vocab:Person ;
    vocab:hasPersonName "TARQ0001 L. Tarquinius Collatinus" ;
    vocab:hasDprrID "TARQ0001" ;
    vocab:hasID "2" ;
    vocab:hasNomen "Tarquinius" ;
    vocab:hasCognomen "Collatinus" ;
    vocab:isSex <http://romanrepublic.ac.uk/rdf/entity/Sex/Male> .

<http://romanrepublic.ac.uk/rdf/entity/PostAssertion/1> a vocab:PostAssertion ;
    vocab:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/1> ;
    vocab:hasOffice <http://romanrepublic.ac.uk/rdf/entity/Office/3> ;
    vocab:hasDateStart "-509"^^xsd:integer ;
    vocab:hasDateEnd "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/PostAssertion/2> a vocab:PostAssertion ;
    vocab:isAboutPerson <http://romanrepublic.ac.uk/rdf/entity/Person/2> ;
    vocab:hasOffice <http://romanrepublic.ac.uk/rdf/entity/Office/3> ;
    vocab:hasDateStart "-509"^^xsd:integer ;
    vocab:hasDateEnd "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/Office/3> a vocab:Office ;
    rdfs:label "Office: consul" .

<http://romanrepublic.ac.uk/rdf/entity/Sex/Male> a vocab:Sex ;
    rdfs:label "Sex: Male" .
"""


def test_get_or_create_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store = get_or_create_store(store_path)
        assert store is not None


def test_load_rdf_returns_triple_count():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store = get_or_create_store(store_path)
        ttl_path = Path(tmpdir) / "test.ttl"
        ttl_path.write_text(SAMPLE_TURTLE)
        count = load_rdf(store, ttl_path)
        assert count > 0


def test_execute_query_returns_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store = get_or_create_store(store_path)
        ttl_path = Path(tmpdir) / "test.ttl"
        ttl_path.write_text(SAMPLE_TURTLE)
        load_rdf(store, ttl_path)

        results = execute_query(
            store,
            """
            PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
            SELECT ?person ?name WHERE {
                ?person a vocab:Person ;
                    vocab:hasPersonName ?name .
            }
            ORDER BY ?name
            """,
        )
        assert len(results) == 2
        assert results[0]["name"] == "IUNI0001 L. Iunius Brutus"
        assert results[1]["name"] == "TARQ0001 L. Tarquinius Collatinus"


def test_execute_query_empty_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store = get_or_create_store(store_path)
        ttl_path = Path(tmpdir) / "test.ttl"
        ttl_path.write_text(SAMPLE_TURTLE)
        load_rdf(store, ttl_path)

        results = execute_query(
            store,
            """
            PREFIX vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/>
            SELECT ?person WHERE {
                ?person a vocab:Person ;
                    vocab:hasNomen "Nonexistent" .
            }
            """,
        )
        assert results == []


def test_is_initialized():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        assert not is_initialized(store_path)
        store = get_or_create_store(store_path)
        ttl_path = Path(tmpdir) / "test.ttl"
        ttl_path.write_text(SAMPLE_TURTLE)
        load_rdf(store, ttl_path)
        assert is_initialized(store_path)


def test_execute_query_non_select_raises():
    """Non-SELECT queries (ASK, CONSTRUCT) raise ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store = get_or_create_store(store_path)
        ttl_path = Path(tmpdir) / "test.ttl"
        ttl_path.write_text(SAMPLE_TURTLE)
        load_rdf(store, ttl_path)

        with pytest.raises(ValueError, match="Only SELECT queries are supported"):
            execute_query(
                store,
                "ASK { ?s ?p ?o }",
            )
