"""MCP server exposing DPRR SPARQL tools over streamable-http."""

from __future__ import annotations

import asyncio
import difflib
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass

import toons
from mcp.server.fastmcp import Context, FastMCP
from pyoxigraph import Store

from dprr_mcp.context import (
    get_cross_cutting_tips,
    get_relevant_examples,
    get_relevant_tips,
    load_examples,
    load_prefixes,
    load_schemas,
    load_tips,
    render_class_summary,
    render_examples,
    render_tips,
)
from dprr_mcp.store import ensure_initialized
from dprr_mcp.validate import (
    build_schema_dict,
    extract_query_classes,
    parse_and_fix_prefixes,
    validate_and_execute,
    validate_semantics,
)

logger = logging.getLogger(__name__)

QUERY_TIMEOUT = int(os.environ.get("DPRR_QUERY_TIMEOUT", "600"))


@dataclass
class AppContext:
    store: Store
    prefix_map: dict[str, str]
    schema_dict: dict
    schemas: dict
    examples: list[dict]
    tips: list[dict]


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize the Oxigraph store and schema on startup."""
    store = ensure_initialized()
    prefix_map = load_prefixes()
    schemas = load_schemas()
    examples = load_examples()
    tips = load_tips()
    schema_dict = build_schema_dict(schemas, prefix_map)
    for ex in examples:
        ex["classes"] = extract_query_classes(ex["sparql"], schema_dict)
    yield AppContext(
        store=store,
        prefix_map=prefix_map,
        schema_dict=schema_dict,
        schemas=schemas,
        examples=examples,
        tips=tips,
    )


mcp = FastMCP(
    "dprr",
    instructions=(
        "DPRR (Digital Prosopography of the Roman Republic) SPARQL query tools. "
        "Use get_schema to learn the ontology, validate_sparql to check queries, "
        "and execute_sparql to run them against the local RDF store."
    ),
    lifespan=lifespan,
)


@mcp.custom_route("/healthz", ["GET"])
async def healthz(request):
    """Health check endpoint for container orchestrators."""
    from starlette.responses import JSONResponse

    return JSONResponse({"status": "ok"})


@mcp.tool()
def get_schema(ctx: Context) -> str:
    """Get a DPRR ontology overview: namespace prefixes, available classes, and general query tips. Call this first, then use validate_sparql for class-specific guidance and examples."""
    app: AppContext = ctx.request_context.lifespan_context

    prefix_lines = "\n".join(
        f"PREFIX {k}: <{v}>" for k, v in app.prefix_map.items()
    )
    class_summary = render_class_summary(app.schemas)
    cross_tips = get_cross_cutting_tips(app.tips)
    tips_md = render_tips(cross_tips)

    return (
        f"## Prefixes\n\n```sparql\n{prefix_lines}\n```\n\n"
        f"## Classes\n\n{class_summary}\n\n"
        f"## General Tips\n\n{tips_md}"
    )


def _query_context(sparql: str, app: AppContext, *, include_examples: bool = True) -> str:
    """Build contextual tips (and optionally examples) for a SPARQL query."""
    classes = extract_query_classes(sparql, app.schema_dict)
    if not classes:
        return ""

    parts: list[str] = []
    tips = get_relevant_tips(app.tips, classes)
    if tips:
        parts.append(f"## Relevant Tips\n\n{render_tips(tips)}")
    if include_examples:
        examples = get_relevant_examples(app.examples, classes)
        if examples:
            parts.append(f"## Relevant Examples\n\n{render_examples(examples)}")
    if not parts:
        return ""
    return "\n\n---\n\n" + "\n\n".join(parts)


@mcp.tool()
def validate_sparql(ctx: Context, sparql: str) -> str:
    """Validate a SPARQL query against the DPRR schema without executing it. Checks syntax, auto-repairs missing PREFIX declarations, and validates that all classes and predicates exist in the ontology."""
    app: AppContext = ctx.request_context.lifespan_context

    fixed_sparql, parse_errors = parse_and_fix_prefixes(sparql, app.prefix_map)
    if parse_errors:
        error_list = "\n".join(f"- {e}" for e in parse_errors)
        base = f"INVALID\n\nErrors:\n{error_list}"
        return base + _query_context(sparql, app)

    semantic_errors = validate_semantics(fixed_sparql, app.schema_dict)
    if semantic_errors:
        error_list = "\n".join(f"- {e}" for e in semantic_errors)
        base = f"INVALID\n\nErrors:\n{error_list}"
        return base + _query_context(fixed_sparql, app)

    if fixed_sparql != sparql:
        diff = "".join(
            difflib.unified_diff(
                sparql.splitlines(keepends=True),
                fixed_sparql.splitlines(keepends=True),
                n=0,
            )
        )
        base = f"VALID (prefixes auto-repaired)\n\n```diff\n{diff}```"
    else:
        base = "VALID"
    return base + _query_context(fixed_sparql, app)


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
        base = f"ERROR:\n{error_list}"
        return base + _query_context(sparql, app, include_examples=False)

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
