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


@pytest.mark.asyncio
async def test_broadcast_stores_history(manager):
    manager.activate()
    await manager.broadcast("msg1")
    await manager.broadcast("msg2")
    assert len(manager.history) == 2
    assert manager.history[0] == "msg1"
    assert manager.history[1] == "msg2"


@pytest.mark.asyncio
async def test_deactivate_clears_history(manager):
    manager.activate()
    await manager.broadcast("test")
    assert len(manager.history) == 1
    await manager.deactivate()
    assert len(manager.history) == 0
