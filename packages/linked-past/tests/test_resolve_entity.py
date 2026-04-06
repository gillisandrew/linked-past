"""Tests for the standalone resolve_entity function."""
import pytest
from unittest.mock import MagicMock, patch
from linked_past.core.viewer_api import resolve_entity

def _make_mock_registry(ds_name: str | None = "dprr"):
    store = MagicMock()
    registry = MagicMock()
    registry.dataset_for_uri.return_value = ds_name
    registry.get_store.return_value = store
    return registry, store

def test_resolve_entity_returns_none_for_unknown_uri():
    registry = MagicMock()
    registry.dataset_for_uri.return_value = None
    linkage = MagicMock()
    linkage.find_links.return_value = []
    result = resolve_entity("http://unknown.example/thing/1", registry, linkage)
    assert result is None

@patch("linked_past.core.viewer_api.execute_query", return_value=[])
@patch("linked_past.core.server._find_store_xrefs", return_value=[])
def test_resolve_entity_returns_entity_data_dict(mock_xrefs, mock_eq):
    registry, store = _make_mock_registry("dprr")
    linkage = MagicMock()
    linkage.find_links.return_value = []
    result = resolve_entity("http://romanrepublic.ac.uk/person/1", registry, linkage)
    assert result is not None
    assert result["dataset"] == "dprr"
    assert "name" in result
    assert "properties" in result
    assert isinstance(result["properties"], list)
    assert "xrefs" in result
    assert isinstance(result["xrefs"], list)
    assert result["description"] == ""
