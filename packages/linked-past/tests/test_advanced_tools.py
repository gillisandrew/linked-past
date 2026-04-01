"""Tests for advanced MCP tools and registry helpers."""

from pathlib import Path

import pytest
from linked_past.core.registry import DatasetRegistry
from linked_past.core.store import create_store, execute_query

DPRR_TURTLE = """\
@prefix vocab: <http://romanrepublic.ac.uk/rdf/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://romanrepublic.ac.uk/rdf/entity/Person/1> a vocab:Person ;
    vocab:hasPersonName "IUNI0001 L. Iunius Brutus" ;
    vocab:hasNomen "Iunius" .

<http://romanrepublic.ac.uk/rdf/entity/Person/2> a vocab:Person ;
    vocab:hasPersonName "IUNI0002 M. Iunius Brutus" ;
    vocab:hasNomen "Iunius" .

<http://romanrepublic.ac.uk/rdf/entity/Office/3> a vocab:Office ;
    rdfs:label "Office: consul" .
"""


@pytest.fixture
def dprr_store(tmp_path):
    store_path = tmp_path / "store"
    store = create_store(store_path)
    ttl = tmp_path / "data.ttl"
    ttl.write_text(DPRR_TURTLE)
    from pyoxigraph import RdfFormat

    store.bulk_load(path=str(ttl), format=RdfFormat.TURTLE)
    return store


def test_dataset_for_uri():
    reg = DatasetRegistry(data_dir=Path("/tmp"))
    assert reg.dataset_for_uri("http://romanrepublic.ac.uk/rdf/entity/Person/1") == "dprr"
    assert reg.dataset_for_uri("https://pleiades.stoa.org/places/423025") == "pleiades"
    assert reg.dataset_for_uri("http://nomisma.org/id/augustus") == "nomisma"
    assert reg.dataset_for_uri("http://n2t.net/ark:/99152/p05krdxmkzt") == "periodo"
    assert reg.dataset_for_uri("http://example.org/unknown") is None


def test_dataset_for_uri_unregistered():
    """URI matches namespace even when plugin is not registered (pure namespace lookup)."""
    reg = DatasetRegistry(data_dir=Path("/tmp"))
    assert reg.dataset_for_uri("http://romanrepublic.ac.uk/rdf/entity/Person/1") == "dprr"


def test_search_entities_query(dprr_store):
    """Verify the SPARQL pattern for entity search works."""
    sparql = """
    PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT DISTINCT ?uri ?label ?type WHERE {
        { ?uri rdfs:label ?label } UNION { ?uri skos:prefLabel ?label }
        FILTER(CONTAINS(LCASE(STR(?label)), "consul"))
        OPTIONAL { ?uri a ?type }
    }
    """
    results = execute_query(dprr_store, sparql)
    assert len(results) >= 1
    assert any("consul" in r["label"].lower() for r in results)


def test_explore_entity_query(dprr_store):
    """Verify the SPARQL pattern for entity exploration works."""
    sparql = """
    SELECT ?pred ?obj WHERE {
        <http://romanrepublic.ac.uk/rdf/entity/Person/1> ?pred ?obj .
    }
    """
    results = execute_query(dprr_store, sparql)
    assert len(results) > 0
    preds = {r["pred"] for r in results}
    assert "http://romanrepublic.ac.uk/rdf/ontology#hasPersonName" in preds
