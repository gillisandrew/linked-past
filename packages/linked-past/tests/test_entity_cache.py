"""Tests for entity cache generation after viewer pushes."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from linked_past.core.server import _push_to_viewer, AppContext


@pytest.fixture
def mock_app():
    viewer = MagicMock()
    viewer.is_active = True
    viewer.session_id = "test-session"
    viewer.next_seq.return_value = 1
    viewer.broadcast = AsyncMock()
    viewer.resolved_uris = set()

    registry = MagicMock()
    registry.dataset_for_uri.return_value = None
    registry.get_store.return_value = MagicMock()

    linkage = MagicMock()
    linkage.find_links.return_value = []

    app = AppContext(registry=registry, linkage=linkage)
    app.viewer = viewer
    return app


@pytest.mark.asyncio
async def test_push_to_viewer_writes_entity_cache(mock_app):
    """After a query with entity URIs, an entity_cache message should follow."""
    mock_app.registry.dataset_for_uri.side_effect = lambda uri: (
        "dprr" if "romanrepublic" in uri else None
    )
    data = {
        "rows": [{"person": "http://romanrepublic.ac.uk/person/1", "name": "Cicero"}],
        "columns": ["person", "name"], "sparql": "SELECT ...", "row_count": 1,
    }
    await _push_to_viewer(mock_app, "query", "dprr", data)
    assert mock_app.viewer.broadcast.call_count == 2
    cache_msg = json.loads(mock_app.viewer.broadcast.call_args_list[1][0][0])
    assert cache_msg["type"] == "entity_cache"
    assert "http://romanrepublic.ac.uk/person/1" in cache_msg["data"]["entities"]


@pytest.mark.asyncio
async def test_push_to_viewer_skips_cache_when_no_uris(mock_app):
    data = {"title": "Report", "markdown": "No entities here."}
    await _push_to_viewer(mock_app, "report", None, data)
    assert mock_app.viewer.broadcast.call_count == 1


@pytest.mark.asyncio
async def test_push_to_viewer_deduplicates_resolved_uris(mock_app):
    mock_app.viewer.resolved_uris.add("http://romanrepublic.ac.uk/person/1")
    data = {
        "rows": [{"person": "http://romanrepublic.ac.uk/person/1"}],
        "columns": ["person"], "sparql": "SELECT ...", "row_count": 1,
    }
    await _push_to_viewer(mock_app, "query", "dprr", data)
    assert mock_app.viewer.broadcast.call_count == 1
