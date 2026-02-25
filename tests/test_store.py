import tempfile
from pathlib import Path

from dprr_tool.store import get_or_create_store, load_rdf, execute_query, is_initialized


SAMPLE_TURTLE = """\
@prefix vocab: <http://romanrepublic.ac.uk/rdf/entity/vocab/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://romanrepublic.ac.uk/rdf/entity/Person/1> a vocab:Person ;
    rdfs:label "L. Iunius Brutus" ;
    vocab:hasDprrID "IUNI0001" ;
    vocab:hasNomen "Iunius" ;
    vocab:hasCognomen "Brutus" ;
    vocab:isSex <http://romanrepublic.ac.uk/rdf/entity/Sex/Male> ;
    vocab:hasEraFrom "-509"^^xsd:integer ;
    vocab:hasEraTo "-509"^^xsd:integer .

<http://romanrepublic.ac.uk/rdf/entity/Person/2> a vocab:Person ;
    rdfs:label "L. Tarquinius Collatinus" ;
    vocab:hasDprrID "TARQ0001" ;
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
    rdfs:label "Consul" .

<http://romanrepublic.ac.uk/rdf/entity/Sex/Male> a vocab:Sex ;
    rdfs:label "Male" .
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
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?person ?name WHERE {
                ?person a vocab:Person ;
                    rdfs:label ?name .
            }
            ORDER BY ?name
            """,
        )
        assert len(results) == 2
        assert results[0]["name"] == "L. Iunius Brutus"
        assert results[1]["name"] == "L. Tarquinius Collatinus"


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
