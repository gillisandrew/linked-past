"""MCP server exposing DPRR SPARQL tools over stdio or streamable-http."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

from dprr_tool.context import (
    load_examples,
    load_prefixes,
    load_schemas,
    load_tips,
    render_examples,
    render_schemas_as_shex,
    render_tips,
)
from dprr_tool.store import ensure_initialized, execute_query
from dprr_tool.validate import (
    build_schema_dict,
    parse_and_fix_prefixes,
    validate_and_execute,
)

logger = logging.getLogger(__name__)

QUERY_TIMEOUT = int(os.environ.get("DPRR_QUERY_TIMEOUT", "60"))

DEFAULT_STORE_PATH = Path.home() / ".dprr-tool" / "store"


@dataclass
class AppContext:
    store: object  # pyoxigraph.Store
    prefix_map: dict[str, str]
    schema_dict: dict


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize the Oxigraph store and schema on startup."""
    store_path = Path(os.environ.get("DPRR_STORE_PATH", str(DEFAULT_STORE_PATH)))
    store = ensure_initialized(store_path)
    prefix_map = load_prefixes()
    schemas = load_schemas()
    schema_dict = build_schema_dict(schemas, prefix_map)
    yield AppContext(store=store, prefix_map=prefix_map, schema_dict=schema_dict)


mcp = FastMCP(
    "dprr",
    instructions=(
        "DPRR (Digital Prosopography of the Roman Republic) SPARQL query tools. "
        "Use get_schema to learn the ontology, validate_sparql to check queries, "
        "and execute_sparql to run them against the local RDF store."
    ),
    lifespan=lifespan,
)


@mcp.tool()
def get_schema(ctx: Context) -> str:
    """Get the full DPRR ontology context: namespace prefixes, ShEx schema for all classes/properties, 28 curated example question/SPARQL pairs, and query tips for common pitfalls. Call this first to learn the domain before generating queries."""
    prefix_map = load_prefixes()
    schemas = load_schemas()
    examples = load_examples()
    tips = load_tips()

    return json.dumps(
        {
            "prefixes": prefix_map,
            "schema_shex": render_schemas_as_shex(schemas),
            "examples": render_examples(examples),
            "query_tips": render_tips(tips),
        },
        indent=2,
    )


@mcp.tool()
def validate_sparql(ctx: Context, sparql: str) -> str:
    """Validate a SPARQL query against the DPRR schema without executing it. Checks syntax, auto-repairs missing PREFIX declarations, and validates that all classes and predicates exist in the ontology."""
    app: AppContext = ctx.request_context.lifespan_context

    fixed_sparql, parse_errors = parse_and_fix_prefixes(sparql, app.prefix_map)
    if parse_errors:
        return json.dumps(
            {"valid": False, "fixed_sparql": fixed_sparql, "errors": parse_errors}
        )

    from dprr_tool.validate import validate_semantics

    semantic_errors = validate_semantics(fixed_sparql, app.schema_dict)
    return json.dumps(
        {
            "valid": len(semantic_errors) == 0,
            "fixed_sparql": fixed_sparql,
            "errors": semantic_errors,
        }
    )


@mcp.tool()
async def execute_sparql(ctx: Context, sparql: str, timeout: int | None = None) -> str:
    """Validate and execute a SPARQL query against the local DPRR RDF store. Returns results as rows of column/value pairs. Automatically repairs missing PREFIX declarations before execution."""
    app: AppContext = ctx.request_context.lifespan_context
    effective_timeout = timeout if timeout is not None else QUERY_TIMEOUT

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                validate_and_execute, sparql, app.store, app.schema_dict, app.prefix_map
            ),
            timeout=effective_timeout,
        )
    except asyncio.TimeoutError:
        logger.warning("Query timed out after %ds: %s", effective_timeout, sparql[:200])
        return json.dumps(
            {
                "success": False,
                "sparql": sparql,
                "rows": [],
                "row_count": 0,
                "errors": [f"Query timed out after {effective_timeout}s. Simplify the query or increase the timeout."],
            }
        )
    except OSError as e:
        logger.error("Store error: %s", e)
        return json.dumps(
            {
                "success": False,
                "sparql": sparql,
                "rows": [],
                "row_count": 0,
                "errors": [f"Store access error: {e}"],
            }
        )
    except Exception as e:
        logger.error("Unexpected error executing query: %s", e)
        return json.dumps(
            {
                "success": False,
                "sparql": sparql,
                "rows": [],
                "row_count": 0,
                "errors": [f"Unexpected error: {e}"],
            }
        )

    return json.dumps(
        {
            "success": result.success,
            "sparql": result.sparql,
            "rows": result.rows,
            "row_count": len(result.rows),
            "errors": result.errors,
        }
    )


def main():
    """Run the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="DPRR MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP transport (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP transport (default: 8000)")
    args = parser.parse_args()

    if args.transport == "http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
