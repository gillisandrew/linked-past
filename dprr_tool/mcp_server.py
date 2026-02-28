"""MCP server exposing DPRR SPARQL tools over streamable-http."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import toons
from mcp.server.fastmcp import Context, FastMCP

from dprr_tool.context import (
    load_examples,
    load_prefixes,
    load_schemas,
    load_tips,
)
from dprr_tool.store import ensure_initialized, execute_query
from dprr_tool.validate import (
    build_schema_dict,
    parse_and_fix_prefixes,
    validate_and_execute,
)

logger = logging.getLogger(__name__)

QUERY_TIMEOUT = int(os.environ.get("DPRR_QUERY_TIMEOUT", "120"))

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
    return toons.dumps({
        "prefixes": load_prefixes(),
        "schema": load_schemas(),
        "examples": load_examples(),
        "tips": load_tips(),
    })


@mcp.tool()
def validate_sparql(ctx: Context, sparql: str) -> str:
    """Validate a SPARQL query against the DPRR schema without executing it. Checks syntax, auto-repairs missing PREFIX declarations, and validates that all classes and predicates exist in the ontology."""
    app: AppContext = ctx.request_context.lifespan_context

    fixed_sparql, parse_errors = parse_and_fix_prefixes(sparql, app.prefix_map)
    if parse_errors:
        error_list = "\n".join(f"- {e}" for e in parse_errors)
        return f"INVALID\n\nErrors:\n{error_list}"

    from dprr_tool.validate import validate_semantics

    semantic_errors = validate_semantics(fixed_sparql, app.schema_dict)
    if semantic_errors:
        error_list = "\n".join(f"- {e}" for e in semantic_errors)
        return f"INVALID\n\nErrors:\n{error_list}"

    if fixed_sparql != sparql:
        return f"VALID (prefixes auto-repaired)\n\n```sparql\n{fixed_sparql}\n```"
    return "VALID"


@mcp.tool()
async def execute_sparql(ctx: Context, sparql: str, timeout: int | None = None) -> str:
    """Validate and execute a SPARQL query against the local DPRR RDF store. Returns results in toons format. Automatically repairs missing PREFIX declarations before execution."""
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
        return f"ERROR: Query timed out after {effective_timeout}s. Simplify the query or increase the timeout."
    except OSError as e:
        logger.error("Store error: %s", e)
        return f"ERROR: Store access error: {e}"
    except Exception as e:
        logger.error("Unexpected error executing query: %s", e)
        return f"ERROR: Unexpected error: {e}"

    if not result.success:
        error_list = "\n".join(f"- {e}" for e in result.errors)
        return f"ERROR:\n{error_list}"

    return toons.dumps(result.rows)


def main():
    """Run the MCP server over streamable-http."""
    import argparse

    parser = argparse.ArgumentParser(description="DPRR MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    args = parser.parse_args()

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
