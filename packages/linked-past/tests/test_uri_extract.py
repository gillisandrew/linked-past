"""Tests for URI extraction from viewer messages."""
import re
from linked_past.core.uri_extract import extract_entity_uris

def test_extract_from_query_rows():
    data = {
        "rows": [
            {"person": "http://romanrepublic.ac.uk/person/1", "name": "Cicero"},
            {"person": "http://romanrepublic.ac.uk/person/2", "name": "Caesar"},
            {"count": 42},
        ],
        "columns": ["person", "name"], "sparql": "SELECT ...", "row_count": 2,
    }
    uris = extract_entity_uris("query", data)
    assert "http://romanrepublic.ac.uk/person/1" in uris
    assert "http://romanrepublic.ac.uk/person/2" in uris
    assert len(uris) == 2

def test_extract_from_search_results():
    data = {"query_text": "cicero", "results": [
        {"uri": "http://romanrepublic.ac.uk/person/1", "label": "Cicero", "dataset": "dprr"},
    ]}
    uris = extract_entity_uris("search", data)
    assert uris == {"http://romanrepublic.ac.uk/person/1"}

def test_extract_from_entity_data():
    data = {
        "uri": "http://romanrepublic.ac.uk/person/1", "name": "Cicero", "dataset": "dprr",
        "properties": [
            {"pred": "http://example.org/hasOffice", "obj": "http://romanrepublic.ac.uk/office/consul"},
            {"pred": "http://example.org/name", "obj": "Marcus Tullius Cicero"},
        ],
        "xrefs": [{"target": "http://nomisma.org/id/cicero", "relationship": "skos:closeMatch", "confidence": "confirmed", "basis": "curated"}],
        "see_also": ["http://en.wikipedia.org/wiki/Cicero"],
    }
    uris = extract_entity_uris("entity", data)
    assert "http://romanrepublic.ac.uk/person/1" in uris
    assert "http://romanrepublic.ac.uk/office/consul" in uris
    assert "http://nomisma.org/id/cicero" in uris
    assert "Marcus Tullius Cicero" not in uris
    assert "http://en.wikipedia.org/wiki/Cicero" not in uris

def test_extract_from_links_data():
    data = {"uri": "http://romanrepublic.ac.uk/person/1", "links": [
        {"target": "http://nomisma.org/id/cicero", "relationship": "skos:closeMatch", "confidence": "confirmed", "basis": "curated"},
    ]}
    uris = extract_entity_uris("links", data)
    assert "http://romanrepublic.ac.uk/person/1" in uris
    assert "http://nomisma.org/id/cicero" in uris

def test_extract_from_report_markdown():
    data = {"title": "Analysis", "markdown": "The entity [Cicero](http://romanrepublic.ac.uk/person/1) held office. See also http://nomisma.org/id/rome for context."}
    uris = extract_entity_uris("report", data)
    assert "http://romanrepublic.ac.uk/person/1" in uris
    assert "http://nomisma.org/id/rome" in uris

def test_extract_returns_empty_for_unknown_type():
    uris = extract_entity_uris("unknown_type", {})
    assert uris == set()
