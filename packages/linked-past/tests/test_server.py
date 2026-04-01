# tests/test_server.py
from linked_past.core.server import create_mcp_server


def test_build_app_context(patched_app_context):
    ctx = patched_app_context
    assert "dprr" in ctx.registry.list_datasets()
    store = ctx.registry.get_store("dprr")
    assert store is not None


def test_create_mcp_server():
    mcp = create_mcp_server()
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert "discover_datasets" in tool_names
    assert "get_schema" in tool_names
    assert "validate_sparql" in tool_names
    assert "query" in tool_names
    assert "disambiguate" in tool_names
