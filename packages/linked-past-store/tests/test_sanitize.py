"""Tests for RDF sanitization."""

from linked_past_store.sanitize import sanitize_turtle


def test_fix_long_language_subtag(tmp_path):
    """BCP 47 subtags > 8 chars are truncated."""
    ttl = tmp_path / "input.ttl"
    ttl.write_text('@prefix ex: <http://example.org/> .\nex:Thing ex:name "Vatl"@etruscan-in-latin-characters .\n')

    result = sanitize_turtle(ttl, tmp_path / "output.ttl")

    assert result.fixes_applied >= 1
    content = result.output_path.read_text()
    # Subtag should be truncated to max 8 chars each
    assert "etruscan-in-latin" not in content or all(
        len(part) <= 8 for part in content.split("@")[-1].strip().rstrip(" .").split("-")
    )


def test_fix_bare_doi(tmp_path):
    """Bare DOIs get https:// prepended."""
    ttl = tmp_path / "input.ttl"
    ttl.write_text('@prefix ex: <http://example.org/> .\nex:Thing ex:ref <doi.org/10.1234/test> .\n')

    result = sanitize_turtle(ttl, tmp_path / "output.ttl")

    assert result.fixes_applied >= 1
    content = result.output_path.read_text()
    assert "<https://doi.org/10.1234/test>" in content


def test_no_fixes_needed(tmp_path):
    """Clean Turtle returns zero fixes."""
    ttl = tmp_path / "input.ttl"
    ttl.write_text('@prefix ex: <http://example.org/> .\nex:Thing ex:name "Hello"@en .\n')

    result = sanitize_turtle(ttl, tmp_path / "output.ttl")

    assert result.fixes_applied == 0


def test_overwrite_in_place(tmp_path):
    """Without output_path, overwrites input."""
    ttl = tmp_path / "data.ttl"
    ttl.write_text('@prefix ex: <http://example.org/> .\nex:Thing ex:ref <doi.org/10.1234/x> .\n')

    result = sanitize_turtle(ttl)

    assert result.output_path == ttl
    assert result.fixes_applied >= 1
    assert "<https://doi.org/" in ttl.read_text()
