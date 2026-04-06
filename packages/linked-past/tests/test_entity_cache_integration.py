"""Integration test: tool call produces entity_cache message."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from linked_past.core.server import _push_to_viewer, AppContext


@pytest.mark.asyncio
async def test_query_with_entity_uris_produces_cache():
    """A query containing entity URIs should produce an entity_cache broadcast."""
    broadcasts = []
    viewer = MagicMock()
    viewer.is_active = True
    viewer.session_id = "integration-test"
    viewer.next_seq.return_value = 1
    viewer.resolved_uris = set()

    async def capture_broadcast(msg):
        broadcasts.append(json.loads(msg))

    viewer.broadcast = capture_broadcast

    store = MagicMock()

    registry = MagicMock()
    registry.dataset_for_uri.side_effect = lambda uri: (
        "dprr" if "romanrepublic" in uri else None
    )
    registry.get_store.return_value = store

    linkage = MagicMock()
    linkage.find_links.return_value = []

    app = AppContext(registry=registry, linkage=linkage)
    app.viewer = viewer

    await _push_to_viewer(app, "query", "dprr", {
        "rows": [{"person": "http://romanrepublic.ac.uk/person/1"}],
        "columns": ["person"],
        "sparql": "SELECT ...",
        "row_count": 1,
    })

    assert len(broadcasts) == 2
    assert broadcasts[0]["type"] == "query"
    assert broadcasts[1]["type"] == "entity_cache"
    assert "http://romanrepublic.ac.uk/person/1" in broadcasts[1]["data"]["entities"]
    assert "http://romanrepublic.ac.uk/person/1" in viewer.resolved_uris
