# tests/test_multi_dataset_integration.py
"""Cross-cutting integration tests: all plugins load and server registers them."""

from linked_past.core.registry import discover_plugins
from linked_past.core.server import create_mcp_server

EXPECTED_DATASETS = {"dprr", "pleiades", "periodo", "nomisma", "crro", "ocre", "edh"}


def test_discover_finds_all_datasets():
    plugins = discover_plugins()
    names = {p.name for p in plugins}
    assert names == EXPECTED_DATASETS


def test_server_registers_all_plugins():
    mcp = create_mcp_server()
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert "discover_datasets" in tool_names
    assert "query" in tool_names
