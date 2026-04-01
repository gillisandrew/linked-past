"""Tests for viewer HTML fragment renderers."""

from linked_past.core.viewer_render import (
    render_entity_card,
    render_feed_item,
    render_generic,
    render_query_table,
    render_xref_list,
)


def test_render_query_table_basic():
    rows = [{"name": "Caesar", "office": "consul"}, {"name": "Pompey", "office": "consul"}]
    html = render_query_table(rows, dataset="dprr")
    assert "<table" in html
    assert "Caesar" in html
    assert "Pompey" in html
    assert "<th" in html


def test_render_query_table_empty():
    html = render_query_table([], dataset="dprr")
    assert "No results" in html


def test_render_entity_card_person():
    properties = [
        {"pred": "hasPersonName", "obj": "Gaius Julius Caesar"},
        {"pred": "hasEraFrom", "obj": "-100"},
        {"pred": "hasHighestOffice", "obj": "dictator"},
    ]
    html = render_entity_card(
        uri="http://romanrepublic.ac.uk/rdf/entity/Person/1957",
        properties=properties,
        dataset="dprr",
        xrefs=[],
    )
    assert "entity-card" in html
    assert "Gaius Julius Caesar" in html
    assert "dprr" in html


def test_render_entity_card_with_xrefs():
    properties = [{"pred": "label", "obj": "Roma"}]
    xrefs = [
        {"target": "http://nomisma.org/id/rome", "relationship": "skos:closeMatch",
         "confidence": "confirmed", "basis": "Wikidata concordance"},
    ]
    html = render_entity_card(
        uri="https://pleiades.stoa.org/places/423025",
        properties=properties,
        dataset="pleiades",
        xrefs=xrefs,
    )
    assert "Roma" in html
    assert "nomisma.org" in html
    assert "confirmed" in html


def test_render_xref_list():
    links = [
        {"target": "http://nomisma.org/id/pompey", "relationship": "skos:closeMatch",
         "confidence": "confirmed", "basis": "Manual alignment"},
        {"target": "http://example.org/candidate", "relationship": "owl:sameAs",
         "confidence": "candidate", "basis": "Automated match"},
    ]
    html = render_xref_list(links)
    assert "confirmed" in html
    assert "candidate" in html
    assert "nomisma.org" in html


def test_render_generic():
    html = render_generic("Some plain text output from a tool")
    assert "generic-result" in html
    assert "Some plain text output" in html


def test_render_generic_escapes_html():
    html = render_generic("<script>alert('xss')</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_entity_card_escapes_html():
    properties = [{"pred": "<script>", "obj": "<img src=x onerror=alert(1)>"}]
    html = render_entity_card(
        uri="javascript:alert(1)",
        properties=properties,
        dataset="test",
        xrefs=[],
    )
    # Angle brackets must be escaped — no raw HTML tags
    assert "<script>" not in html
    assert "<img " not in html
    assert "&lt;script&gt;" in html
    assert "&lt;img " in html


def test_render_feed_item_no_dataset():
    html = render_feed_item(tool_name="validate_sparql", dataset=None, body_html="<p>ok</p>")
    assert "feed-item" in html
    assert "data-ds" not in html
    assert "<p>ok</p>" in html


def test_render_feed_item():
    html = render_feed_item(
        tool_name="query",
        dataset="dprr",
        body_html="<p>test</p>",
    )
    assert "feed-item" in html
    assert "feed-header" in html
    assert "query" in html
    assert 'data-ds="dprr"' in html
    assert "<p>test</p>" in html
    assert "collapse-toggle" in html
