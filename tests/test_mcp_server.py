import asyncio
from unittest.mock import MagicMock, patch

import pytest
import toons

from dprr_mcp.context import load_examples, load_prefixes, load_schemas, load_tips
from dprr_mcp.mcp_server import execute_sparql, get_schema, main, validate_sparql
from dprr_mcp.validate import build_schema_dict

# --- argparse tests ---


def test_main_defaults():
    """main() with no args runs streamable-http on default host/port."""
    with patch("dprr_mcp.mcp_server.mcp") as mock_mcp:
        with patch("sys.argv", ["dprr-server"]):
            main()
        assert mock_mcp.settings.host == "127.0.0.1"
        assert mock_mcp.settings.port == 8000
        mock_mcp.run.assert_called_once_with(transport="streamable-http")


def test_main_custom_host_port():
    """main() with --host/--port sets settings."""
    with patch("dprr_mcp.mcp_server.mcp") as mock_mcp:
        with patch("sys.argv", ["dprr-server", "--host", "0.0.0.0", "--port", "9000"]):
            main()
        assert mock_mcp.settings.host == "0.0.0.0"
        assert mock_mcp.settings.port == 9000
        mock_mcp.run.assert_called_once_with(transport="streamable-http")


# --- toons output tests ---


@pytest.mark.asyncio
async def test_execute_sparql_empty_results():
    """execute_sparql returns empty toons array for empty result set."""
    from dprr_mcp.validate import ValidationResult

    ctx = _make_mock_ctx()
    mock_result = ValidationResult(
        success=True,
        sparql="SELECT ?x WHERE { ?x ?y ?z }",
        rows=[],
        errors=[],
    )

    with patch("dprr_mcp.mcp_server.asyncio.wait_for", return_value=mock_result):
        result_str = await execute_sparql(ctx, "SELECT ?x WHERE { ?x ?y ?z }")

    assert toons.loads(result_str) == []


@pytest.mark.asyncio
async def test_execute_sparql_toons_roundtrip():
    """execute_sparql toons output round-trips back to original rows."""
    from dprr_mcp.validate import ValidationResult

    ctx = _make_mock_ctx()
    rows = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
    mock_result = ValidationResult(
        success=True,
        sparql="SELECT ?name ?age WHERE { ?x ?y ?z }",
        rows=rows,
        errors=[],
    )

    with patch("dprr_mcp.mcp_server.asyncio.wait_for", return_value=mock_result):
        result_str = await execute_sparql(ctx, "SELECT ?name ?age WHERE { ?x ?y ?z }")

    assert toons.loads(result_str) == rows


# --- execute_sparql timeout and error handling tests ---


def _make_mock_ctx(store=None, prefix_map=None, schema_dict=None):
    """Create a mock Context with AppContext."""
    from dprr_mcp.mcp_server import AppContext

    app = AppContext(
        store=store or MagicMock(),
        prefix_map=prefix_map or {},
        schema_dict=schema_dict or {},
        schemas={},
        examples=[],
        tips=[],
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

    with patch("dprr_mcp.mcp_server.QUERY_TIMEOUT", 0.1), \
         patch("dprr_mcp.mcp_server.asyncio.to_thread", side_effect=slow_thread):
        result_str = await execute_sparql(ctx, "SELECT ?x WHERE { ?x ?y ?z }")

    assert result_str.startswith("ERROR:")
    assert "timed out" in result_str


@pytest.mark.asyncio
async def test_execute_sparql_os_error():
    """execute_sparql returns error text on OSError."""
    ctx = _make_mock_ctx()

    async def raise_os_error(*args, **kwargs):
        raise OSError("store locked")

    with patch("dprr_mcp.mcp_server.asyncio.to_thread", side_effect=raise_os_error):
        result_str = await execute_sparql(ctx, "SELECT ?x WHERE { ?x ?y ?z }")

    assert result_str.startswith("ERROR:")
    assert "Store access error" in result_str


@pytest.mark.asyncio
async def test_execute_sparql_unexpected_error():
    """execute_sparql returns error text on unexpected exceptions."""
    ctx = _make_mock_ctx()

    async def raise_unexpected(*args, **kwargs):
        raise RuntimeError("something broke")

    with patch("dprr_mcp.mcp_server.asyncio.to_thread", side_effect=raise_unexpected):
        result_str = await execute_sparql(ctx, "SELECT ?x WHERE { ?x ?y ?z }")

    assert result_str.startswith("ERROR:")
    assert "Unexpected error" in result_str


@pytest.mark.asyncio
async def test_execute_sparql_success():
    """execute_sparql returns toons-formatted output on success."""
    from dprr_mcp.validate import ValidationResult

    ctx = _make_mock_ctx()
    mock_result = ValidationResult(
        success=True,
        sparql="SELECT ?x WHERE { ?x ?y ?z }",
        rows=[{"x": "http://example.com/1"}],
        errors=[],
    )

    with patch("dprr_mcp.mcp_server.asyncio.wait_for", return_value=mock_result):
        result_str = await execute_sparql(ctx, "SELECT ?x WHERE { ?x ?y ?z }")

    parsed = toons.loads(result_str)
    assert parsed == [{"x": "http://example.com/1"}]


# --- get_schema tests ---


def _make_full_ctx():
    """Create a mock Context with real YAML data loaded."""
    from dprr_mcp.mcp_server import AppContext

    prefix_map = load_prefixes()
    schemas = load_schemas()
    examples = load_examples()
    tips = load_tips()
    schema_dict = build_schema_dict(schemas, prefix_map)
    app = AppContext(
        store=MagicMock(),
        prefix_map=prefix_map,
        schema_dict=schema_dict,
        schemas=schemas,
        examples=examples,
        tips=tips,
    )
    ctx = MagicMock()
    ctx.request_context.lifespan_context = app
    return ctx


def test_get_schema_returns_toons():
    """get_schema returns valid toons with all expected keys."""
    ctx = _make_full_ctx()
    result_str = get_schema(ctx)
    parsed = toons.loads(result_str)
    assert "prefixes" in parsed
    assert "schema" in parsed
    assert "examples" in parsed
    assert "tips" in parsed


def test_get_schema_contains_data():
    """get_schema output contains actual ontology data."""
    ctx = _make_full_ctx()
    parsed = toons.loads(get_schema(ctx))
    assert "vocab" in parsed["prefixes"]
    assert "Person" in parsed["schema"]
    assert len(parsed["examples"]) >= 15
    assert len(parsed["tips"]) >= 7


# --- validate_sparql tests ---


def test_validate_sparql_valid_query():
    """validate_sparql returns VALID for a correct query."""
    ctx = _make_full_ctx()
    result = validate_sparql(
        ctx,
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:Person }",
    )
    assert result == "VALID"


def test_validate_sparql_invalid_syntax():
    """validate_sparql returns INVALID for bad syntax."""
    ctx = _make_full_ctx()
    result = validate_sparql(ctx, "SELCT ?p WHERE { ?p ?o ?s }")
    assert result.startswith("INVALID")
    assert "Errors:" in result


def test_validate_sparql_prefix_repair():
    """validate_sparql auto-repairs missing PREFIX and reports valid."""
    ctx = _make_full_ctx()
    result = validate_sparql(ctx, "SELECT ?p WHERE { ?p a vocab:Person }")
    assert "VALID" in result
    assert "prefixes auto-repaired" in result
    assert "PREFIX vocab:" in result


def test_validate_sparql_semantic_error():
    """validate_sparql catches invalid predicates."""
    ctx = _make_full_ctx()
    result = validate_sparql(
        ctx,
        "PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>\n"
        "SELECT ?p WHERE { ?p a vocab:Person ; vocab:hasOffice ?o }",
    )
    assert result.startswith("INVALID")
    assert "hasOffice" in result
