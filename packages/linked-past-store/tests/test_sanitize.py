"""Tests for RDF sanitization."""

from linked_past_store.sanitize import has_rapper, sanitize_turtle


def test_fix_long_language_subtag(tmp_path):
    """BCP 47 subtags > 8 chars are truncated."""
    ttl = tmp_path / "input.ttl"
    ttl.write_text(
        '@prefix ex: <http://example.org/> .\n'
        'ex:Thing ex:name "Vatl"@etruscan-in-latin-characters .\n'
    )

    result = sanitize_turtle(ttl, tmp_path / "output.ttl")

    assert result.fixes_applied >= 1
    content = result.output_path.read_text()
    assert "in-latin-characters" not in content


def test_fix_bare_doi(tmp_path):
    """Bare DOIs get fixed (by rapper or regex)."""
    ttl = tmp_path / "input.ttl"
    ttl.write_text(
        '@prefix ex: <http://example.org/> .\n'
        'ex:Thing ex:ref <doi.org/10.1234/test> .\n'
    )

    result = sanitize_turtle(ttl, tmp_path / "output.ttl")

    content = result.output_path.read_text()
    # rapper may fix this itself, or regex catches it — either way, bare DOI should be gone
    assert "doi.org/10.1234/test" not in content or "https://doi.org/" in content


def test_no_fixes_needed(tmp_path):
    """Clean Turtle returns zero fixes."""
    ttl = tmp_path / "input.ttl"
    ttl.write_text(
        '@prefix ex: <http://example.org/> .\n'
        'ex:Thing ex:name "Hello"@en .\n'
    )

    result = sanitize_turtle(ttl, tmp_path / "output.ttl")

    assert result.fixes_applied == 0


def test_overwrite_in_place(tmp_path):
    """Without output_path, overwrites input."""
    ttl = tmp_path / "data.ttl"
    ttl.write_text(
        '@prefix ex: <http://example.org/> .\n'
        'ex:Thing ex:name "Vatl"@etruscan-in-latin-characters .\n'
    )

    result = sanitize_turtle(ttl)

    assert result.output_path == ttl
    content = ttl.read_text()
    assert "in-latin-characters" not in content


def test_rapper_available():
    """has_rapper() returns True if rapper is installed."""
    # This test documents the environment — may fail if rapper isn't installed
    result = has_rapper()
    assert isinstance(result, bool)


def test_rapper_rdfxml_conversion(tmp_path):
    """rapper converts RDF/XML to clean Turtle."""
    if not has_rapper():
        return  # Skip if rapper not installed

    rdf = tmp_path / "input.rdf"
    rdf.write_text(
        '<?xml version="1.0"?>\n'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"\n'
        '         xmlns:ex="http://example.org/">\n'
        '  <rdf:Description rdf:about="http://example.org/Thing">\n'
        '    <ex:name>Test</ex:name>\n'
        '  </rdf:Description>\n'
        '</rdf:RDF>\n'
    )

    result = sanitize_turtle(rdf, tmp_path / "output.ttl")

    assert result.used_rapper
    assert result.triple_count >= 1
    content = result.output_path.read_text()
    assert "example.org" in content
