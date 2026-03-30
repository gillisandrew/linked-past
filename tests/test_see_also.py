"""Tests for the _collect_see_also helper."""
from linked_past.core.server import _collect_see_also


class FakeLinkage:
    def __init__(self, links):
        self._links = links
    def find_links(self, uri):
        return self._links.get(uri, [])


def test_see_also_with_links():
    linkage = FakeLinkage({
        "http://romanrepublic.ac.uk/rdf/entity/Person/1957": [
            {"target": "http://nomisma.org/id/julius_caesar", "confidence": "confirmed", "basis": "RRC"},
        ],
    })
    rows = [{"person": "http://romanrepublic.ac.uk/rdf/entity/Person/1957", "name": "Caesar"}]
    result = _collect_see_also(rows, linkage)
    assert "See also" in result
    assert "julius_caesar" in result


def test_see_also_no_links():
    linkage = FakeLinkage({})
    rows = [{"person": "http://romanrepublic.ac.uk/rdf/entity/Person/9999"}]
    result = _collect_see_also(rows, linkage)
    assert result == ""


def test_see_also_no_uris():
    linkage = FakeLinkage({})
    rows = [{"name": "Caesar", "office": "consul"}]
    result = _collect_see_also(rows, linkage)
    assert result == ""


def test_see_also_none_linkage():
    result = _collect_see_also([{"x": "http://example.org/1"}], None)
    assert result == ""


def test_see_also_deduplicates():
    linkage = FakeLinkage({
        "http://example.org/1": [
            {"target": "http://example.org/a", "confidence": "confirmed"},
        ],
    })
    rows = [{"x": "http://example.org/1"}, {"x": "http://example.org/1"}]
    result = _collect_see_also(rows, linkage)
    assert result.count("example.org/a") == 1
