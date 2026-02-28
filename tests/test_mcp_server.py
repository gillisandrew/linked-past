import asyncio
from unittest.mock import patch, MagicMock

import pytest
import toons

from dprr_tool.mcp_server import main, execute_sparql, QUERY_TIMEOUT


# --- argparse tests ---


def test_main_defaults():
    """main() with no args runs streamable-http on default host/port."""
    with patch("dprr_tool.mcp_server.mcp") as mock_mcp:
        with patch("sys.argv", ["dprr-server"]):
            main()
        assert mock_mcp.settings.host == "127.0.0.1"
        assert mock_mcp.settings.port == 8000
        mock_mcp.run.assert_called_once_with(transport="streamable-http")


def test_main_custom_host_port():
    """main() with --host/--port sets settings."""
    with patch("dprr_tool.mcp_server.mcp") as mock_mcp:
        with patch("sys.argv", ["dprr-server", "--host", "0.0.0.0", "--port", "9000"]):
            main()
        assert mock_mcp.settings.host == "0.0.0.0"
        assert mock_mcp.settings.port == 9000
        mock_mcp.run.assert_called_once_with(transport="streamable-http")


# --- toons output tests ---


@pytest.mark.asyncio
async def test_execute_sparql_empty_results():
    """execute_sparql returns empty toons array for empty result set."""
    from dprr_tool.validate import ValidationResult

    ctx = _make_mock_ctx()
    mock_result = ValidationResult(
        success=True,
        sparql="SELECT ?x WHERE { ?x ?y ?z }",
        rows=[],
        errors=[],
    )

    with patch("dprr_tool.mcp_server.asyncio.wait_for", return_value=mock_result):
        result_str = await execute_sparql(ctx, "SELECT ?x WHERE { ?x ?y ?z }")

    assert toons.loads(result_str) == []


@pytest.mark.asyncio
async def test_execute_sparql_toons_roundtrip():
    """execute_sparql toons output round-trips back to original rows."""
    from dprr_tool.validate import ValidationResult

    ctx = _make_mock_ctx()
    rows = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
    mock_result = ValidationResult(
        success=True,
        sparql="SELECT ?name ?age WHERE { ?x ?y ?z }",
        rows=rows,
        errors=[],
    )

    with patch("dprr_tool.mcp_server.asyncio.wait_for", return_value=mock_result):
        result_str = await execute_sparql(ctx, "SELECT ?name ?age WHERE { ?x ?y ?z }")

    assert toons.loads(result_str) == rows


# --- execute_sparql timeout and error handling tests ---


def _make_mock_ctx(store=None, prefix_map=None, schema_dict=None):
    """Create a mock Context with AppContext."""
    from dprr_tool.mcp_server import AppContext

    app = AppContext(
        store=store or MagicMock(),
        prefix_map=prefix_map or {},
        schema_dict=schema_dict or {},
    )
    ctx = MagicMock()
    ctx.request_context.lifespan_context = app
    return ctx


@pytest.mark.asyncio
async def test_execute_sparql_timeout():
    """execute_sparql returns error text on timeout."""
    ctx = _make_mock_ctx()

    async def slow_thread(*args, **kwargs):
        await asyncio.sleep(10)

    with patch("dprr_tool.mcp_server.QUERY_TIMEOUT", 0.1), \
         patch("dprr_tool.mcp_server.asyncio.to_thread", side_effect=slow_thread):
        result_str = await execute_sparql(ctx, "SELECT ?x WHERE { ?x ?y ?z }")

    assert result_str.startswith("ERROR:")
    assert "timed out" in result_str


@pytest.mark.asyncio
async def test_execute_sparql_os_error():
    """execute_sparql returns error text on OSError."""
    ctx = _make_mock_ctx()

    async def raise_os_error(*args, **kwargs):
        raise OSError("store locked")

    with patch("dprr_tool.mcp_server.asyncio.to_thread", side_effect=raise_os_error):
        result_str = await execute_sparql(ctx, "SELECT ?x WHERE { ?x ?y ?z }")

    assert result_str.startswith("ERROR:")
    assert "Store access error" in result_str


@pytest.mark.asyncio
async def test_execute_sparql_unexpected_error():
    """execute_sparql returns error text on unexpected exceptions."""
    ctx = _make_mock_ctx()

    async def raise_unexpected(*args, **kwargs):
        raise RuntimeError("something broke")

    with patch("dprr_tool.mcp_server.asyncio.to_thread", side_effect=raise_unexpected):
        result_str = await execute_sparql(ctx, "SELECT ?x WHERE { ?x ?y ?z }")

    assert result_str.startswith("ERROR:")
    assert "Unexpected error" in result_str


@pytest.mark.asyncio
async def test_execute_sparql_success():
    """execute_sparql returns toons-formatted output on success."""
    from dprr_tool.validate import ValidationResult

    ctx = _make_mock_ctx()
    mock_result = ValidationResult(
        success=True,
        sparql="SELECT ?x WHERE { ?x ?y ?z }",
        rows=[{"x": "http://example.com/1"}],
        errors=[],
    )

    with patch("dprr_tool.mcp_server.asyncio.wait_for", return_value=mock_result):
        result_str = await execute_sparql(ctx, "SELECT ?x WHERE { ?x ?y ?z }")

    parsed = toons.loads(result_str)
    assert parsed == [{"x": "http://example.com/1"}]
