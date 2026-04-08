"""Tests for DatasetPlugin context retrieval methods."""

from unittest.mock import MagicMock, patch
from linked_past.datasets.base import DatasetPlugin


class FakePlugin(DatasetPlugin):
    """Minimal concrete plugin for testing."""
    name = "test"
    oci_ref = "ghcr.io/test:latest"
    def fetch(self) -> bytes:
        return b""


@patch("linked_past.datasets.base.DatasetPlugin.__init__", return_value=None)
def test_get_relevant_tips_returns_tips_only(mock_init):
    plugin = FakePlugin.__new__(FakePlugin)
    plugin._tips = [
        {"title": "Tip about Person", "body": "Use dprr:hasPersonName", "classes": ["Person"]},
        {"title": "General tip", "body": "Always use LIMIT", "classes": []},
        {"title": "Tip about Office", "body": "Use PostAssertion", "classes": ["PostAssertion"]},
    ]
    plugin._schema_dict = {
        "http://romanrepublic.ac.uk/rdf/ontology#Person": {},
        "http://romanrepublic.ac.uk/rdf/ontology#PostAssertion": {},
    }
    plugin._examples = []

    sparql = "PREFIX dprr: <http://romanrepublic.ac.uk/rdf/ontology#> SELECT ?p WHERE { ?p a dprr:Person }"
    result = plugin.get_relevant_tips(sparql)

    assert "Tip about Person" in result
    assert "Tip about Office" not in result
    assert "```sparql" not in result


@patch("linked_past.datasets.base.DatasetPlugin.__init__", return_value=None)
def test_get_relevant_tips_returns_empty_when_no_classes(mock_init):
    plugin = FakePlugin.__new__(FakePlugin)
    plugin._tips = [{"title": "Tip", "body": "body", "classes": ["Person"]}]
    plugin._schema_dict = {}
    plugin._examples = []

    sparql = "SELECT ?x WHERE { ?x ?p ?o }"
    result = plugin.get_relevant_tips(sparql)
    assert result == ""
