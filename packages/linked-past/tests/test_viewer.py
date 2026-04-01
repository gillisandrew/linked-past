"""Tests for ViewerManager."""

import pytest
from linked_past.core.viewer import ViewerManager


@pytest.fixture
def manager():
    return ViewerManager()


def test_manager_starts_inactive(manager):
    assert not manager.is_active
    assert manager.client_count == 0


@pytest.mark.asyncio
async def test_manager_activate_deactivate(manager):
    manager.activate()
    assert manager.is_active
    await manager.deactivate()
    assert not manager.is_active


@pytest.mark.asyncio
async def test_broadcast_no_clients(manager):
    """Broadcast with no clients should not raise."""
    manager.activate()
    await manager.broadcast("<p>test</p>")


def test_viewer_url(manager):
    assert manager.viewer_url("localhost", 8000) == "http://localhost:8000/viewer"
