"""Tests for RDF verification."""

from linked_past_store.verify import detect_format, verify_turtle

from pyoxigraph import RdfFormat


def test_verify_valid_turtle(tmp_path):
    ttl = tmp_path / "data.ttl"
    ttl.write_text(
        "@prefix ex: <http://example.org/> .\n"
        'ex:Thing1 ex:name "Hello" .\n'
        'ex:Thing2 ex:name "World" .\n'
    )

    result = verify_turtle(ttl)

    assert result.ok
    assert result.triple_count == 2
    assert result.format == "turtle"
    assert result.errors == []


def test_verify_invalid_turtle(tmp_path):
    ttl = tmp_path / "bad.ttl"
    ttl.write_text("this is not valid turtle at all")

    result = verify_turtle(ttl)

    assert not result.ok
    assert result.triple_count == 0
    assert len(result.errors) == 1


def test_verify_empty_file(tmp_path):
    ttl = tmp_path / "empty.ttl"
    ttl.write_text("")

    result = verify_turtle(ttl)

    assert result.ok
    assert result.triple_count == 0


def test_detect_format_turtle(tmp_path):
    ttl = tmp_path / "data.ttl"
    ttl.write_text("@prefix ex: <http://example.org/> .\n")

    assert detect_format(ttl) == RdfFormat.TURTLE


def test_detect_format_rdfxml(tmp_path):
    rdf = tmp_path / "data.rdf"
    rdf.write_text('<?xml version="1.0"?>\n<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/>\n')

    assert detect_format(rdf) == RdfFormat.RDF_XML
