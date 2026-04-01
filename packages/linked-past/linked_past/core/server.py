# linked_past/core/server.py
"""MCP server exposing multi-dataset prosopographical SPARQL tools."""

from __future__ import annotations

import asyncio
import difflib
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import toons
from mcp.server.fastmcp import Context, FastMCP

from linked_past.core.linkage import LinkageGraph
from linked_past.core.registry import DatasetRegistry
from linked_past.core.search import SearchIndex
from linked_past.core.store import get_data_dir
from linked_past.core.validate import parse_and_fix_prefixes, validate_and_execute
from linked_past.datasets.crro.plugin import CRROPlugin
from linked_past.datasets.dprr.plugin import DPRRPlugin
from linked_past.datasets.edh.plugin import EDHPlugin
from linked_past.datasets.nomisma.plugin import NomismaPlugin
from linked_past.datasets.ocre.plugin import OCREPlugin
from linked_past.datasets.periodo.plugin import PeriodOPlugin
from linked_past.datasets.pleiades.plugin import PleiadesPlugin

logger = logging.getLogger(__name__)

QUERY_TIMEOUT = int(os.environ.get("LINKED_PAST_QUERY_TIMEOUT", os.environ.get("DPRR_QUERY_TIMEOUT", "600")))


@dataclass
class AppContext:
    registry: DatasetRegistry
    linkage: LinkageGraph | None = None
    search: SearchIndex | None = None
    meta: object = None  # MetaEntityIndex
    session_log: list = None
    viewer: object = None  # ViewerManager | None

    def __post_init__(self):
        if self.session_log is None:
            self.session_log = []


def _index_dataset(search: SearchIndex, name: str, plugin: object, store=None) -> None:
    """Index a single dataset's context into the search index."""
    search.add(name, "dataset", f"{plugin.display_name}: {plugin.description}")
    if hasattr(plugin, "_examples"):
        for ex in plugin._examples:
            search.add(name, "example", f"{ex['question']}\n{ex['sparql']}")
    if hasattr(plugin, "_tips"):
        for tip in plugin._tips:
            search.add(name, "tip", f"{tip['title']}: {tip['body']}")
    if hasattr(plugin, "_schemas"):
        for cls_name, cls_data in plugin._schemas.items():
            label = cls_data.get("label", cls_name)
            uri = cls_data.get("uri", "")
            comment = cls_data.get("comment", "")
            if uri:
                search.add(name, "schema_label", f"{label} ({uri})")
            else:
                search.add(name, "schema_label", label)
            if comment:
                search.add(name, "schema_comment", f"{cls_name}: {comment}")

    # Generate and index ShEx-like shapes
    if hasattr(plugin, "_schemas") and hasattr(plugin, "_prefixes"):
        from linked_past_store.ontology import generate_shex_shapes

        plugin_tips = plugin._tips if hasattr(plugin, "_tips") else []
        shapes = generate_shex_shapes(plugin._schemas, plugin_tips, plugin._prefixes)
        for cls_name, shape_text in shapes.items():
            search.add(name, "shex_shape", shape_text)

    # Index SKOS vocabulary terms if store is available
    if store is None:
        return
    schemes = list(store.query(
        "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
        "SELECT ?scheme (SAMPLE(?sl) AS ?schemeLabel) (COUNT(?c) AS ?n) WHERE { "
        "  ?c a skos:Concept ; skos:inScheme ?scheme . "
        "  OPTIONAL { ?scheme skos:prefLabel ?sl } "
        "} GROUP BY ?scheme HAVING (COUNT(?c) > 1) ORDER BY DESC(?n)"
    ))
    for row in schemes:
        scheme_uri = str(row[0]).strip("<>")
        scheme_label = row[1].value if row[1] else scheme_uri.rsplit("/", 1)[-1]
        concept_count = int(row[2].value)
        limit = "LIMIT 500" if concept_count > 1000 else ""
        concepts = list(store.query(
            "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
            f"SELECT ?label WHERE {{ "
            f"  ?c a skos:Concept ; skos:inScheme <{scheme_uri}> ; skos:prefLabel ?label . "
            f"  FILTER(lang(?label) = 'en' || lang(?label) = '') "
            f"}} {limit}"
        ))
        if not concepts:
            continue
        labels = [r[0].value for r in concepts]
        for i in range(0, len(labels), 50):
            batch = labels[i:i + 50]
            search.add(name, "skos_vocab",
                       f"Vocabulary: {scheme_label} ({concept_count} terms). "
                       f"Values: {', '.join(batch)}")
        described = list(store.query(
            "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
            f"SELECT ?label ?note WHERE {{ "
            f"  ?c a skos:Concept ; skos:inScheme <{scheme_uri}> ; "
            f"     skos:prefLabel ?label . "
            f"  {{ ?c skos:scopeNote ?note }} UNION {{ ?c skos:definition ?note }} "
            f"  FILTER(lang(?label) = 'en' || lang(?label) = '') "
            f"  FILTER(lang(?note) = 'en' || lang(?note) = '') "
            f"}}"
        ))
        for dr in described:
            search.add(name, "skos_concept", f"{dr[0].value}: {dr[1].value}")


def _build_search_index(registry: DatasetRegistry, data_dir: Path) -> SearchIndex | None:
    """Build full-text search index from plugin context and SKOS vocabularies.

    Always rebuilds fresh — FTS5 indexing is fast (no ML model) and avoids
    stale cache issues when datasets are updated between restarts.
    """
    try:
        search_path = data_dir / "search.db"
        # Remove stale DB + WAL/SHM lock files from previous runs
        for suffix in ("", "-wal", "-shm"):
            p = search_path.parent / (search_path.name + suffix)
            if p.exists():
                p.unlink()
        search = SearchIndex(search_path)

        logger.info("Building search index...")
        for name in registry.list_datasets():
            plugin = registry.get_plugin(name)
            try:
                store = registry.get_store(name)
            except KeyError:
                store = None
            _index_dataset(search, name, plugin, store)

        logger.info("Search index built and cached")
        return search
    except Exception as e:
        logger.warning("Failed to build search index: %s", e)
        return None


def build_app_context(*, eager: bool = False, skip_search: bool = True) -> AppContext:
    """Register plugins and return context.

    Args:
        eager: If True, initialize all datasets (may download). If False (default),
               only open datasets already cached locally.
        skip_search: If True, skip search index and meta-entity index build.
                     Useful for tests to avoid startup cost.
    """
    data_dir = get_data_dir()
    registry = DatasetRegistry(data_dir=data_dir)
    registry.register(DPRRPlugin())
    registry.register(PleiadesPlugin())
    registry.register(PeriodOPlugin())
    registry.register(NomismaPlugin())
    registry.register(CRROPlugin())
    registry.register(OCREPlugin())
    registry.register(EDHPlugin())

    if eager:
        registry.initialize_all()
    else:
        registry.initialize_cached()

    # Load linkage graph in-memory (rebuilt from files on each startup — no disk lock)
    linkage = LinkageGraph()
    linkages_dir = Path(__file__).parent.parent / "linkages"
    if linkages_dir.exists():
        for yaml_file in sorted(linkages_dir.glob("*.yaml")):
            linkage.load_yaml(yaml_file)
        # Load Wikidata-derived Turtle concordances
        wikidata_dir = linkages_dir / "wikidata"
        if wikidata_dir.exists():
            for ttl_file in sorted(wikidata_dir.glob("*.ttl")):
                try:
                    linkage.load_turtle(ttl_file)
                except Exception as e:
                    logger.warning("Failed to load concordance %s: %s", ttl_file.name, e)

    search_index = None if skip_search else _build_search_index(registry, data_dir)

    # Build meta-entity index (skip if already cached)
    meta = None
    if not skip_search:
        try:
            from linked_past.core.meta_entities import MetaEntity, MetaEntityIndex

            meta_db = data_dir / "meta_entities.db"
            meta = MetaEntityIndex(meta_db)

            # Check if already populated
            if meta._conn:
                existing = meta._conn.execute("SELECT COUNT(*) FROM meta_entities").fetchone()[0]
            else:
                existing = 0

            if existing > 0:
                # Load from cache
                for row in meta._conn.execute("SELECT * FROM meta_entities"):
                    import json as json_mod

                    entity = MetaEntity(
                        id=row[0], canonical_name=row[1], entity_type=row[2],
                        description=row[3], date_range=row[4],
                        uris=json_mod.loads(row[5]) if row[5] else {},
                        wikidata_qid=row[6],
                    )
                    meta._entities[entity.id] = entity
                    for uris in entity.uris.values():
                        for uri in uris:
                            meta._uri_to_id[uri] = entity.id
                logger.info("Meta-entity index loaded from cache (%d entities)", existing)
            else:
                count = meta.build_from_linkage(linkage, registry)
                logger.info("Built %d meta-entities", count)

                # Add meta-entity descriptions to embedding index
                if search_index and count > 0:
                    for entity in meta.all_entities():
                        search_index.add("_meta", "meta_entity", entity.description)
                    search_index.build()
        except Exception as e:
            logger.warning("Failed to build meta-entities: %s", e)

    return AppContext(registry=registry, linkage=linkage, search=search_index, meta=meta)


# SKOS/OWL predicates that indicate cross-dataset references
_XREF_PREDICATES = [
    "http://www.w3.org/2004/02/skos/core#closeMatch",
    "http://www.w3.org/2004/02/skos/core#exactMatch",
    "http://www.w3.org/2004/02/skos/core#sameAs",
    "http://www.w3.org/2002/07/owl#sameAs",
]


def _find_store_xrefs(uri: str, registry: DatasetRegistry) -> list[dict]:
    """Find cross-references for a URI by querying dataset stores for SKOS/OWL link predicates."""
    ds_name = registry.dataset_for_uri(uri)
    if not ds_name:
        return []
    try:
        store = registry.get_store(ds_name)
    except KeyError:
        return []

    pred_values = " ".join(f"<{p}>" for p in _XREF_PREDICATES)
    sparql = f"""
    SELECT ?pred ?target WHERE {{
        VALUES ?pred {{ {pred_values} }}
        {{ <{uri}> ?pred ?target }} UNION {{ ?target ?pred <{uri}> }}
    }}
    """
    results = []
    try:
        from linked_past.core.store import execute_query
        rows = execute_query(store, sparql)
        for row in rows:
            target = row.get("target", "")
            pred = row.get("pred", "")
            if target and target != uri:
                # Shorten the predicate
                pred_short = pred.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
                results.append({
                    "target": target,
                    "relationship": pred_short,
                    "confidence": "in-data",
                    "basis": f"Declared in {ds_name} dataset",
                    "source": ds_name,
                })
    except Exception as e:
        logger.warning("Failed to query store xrefs for %s: %s", uri, e)
    return results


def _log_tool_call(app: AppContext, tool_name: str, inputs: dict, result: str, duration_ms: int = 0):
    """Append a tool call to the session log."""
    from datetime import datetime, timezone

    # Summarize the result (don't store full output for large results)
    if len(result) > 2000:
        output_summary = result[:500] + f"\n... ({len(result)} chars total)"
    else:
        output_summary = result

    entry = {
        "id": f"entry_{len(app.session_log) + 1:03d}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "inputs": {k: v for k, v in inputs.items() if v is not None},
        "output_preview": output_summary,
        "output_length": len(result),
        "duration_ms": duration_ms,
    }
    dataset = inputs.get("dataset")
    if dataset:
        meta = app.registry.get_metadata(dataset)
        if meta:
            entry["dataset_version"] = meta
    app.session_log.append(entry)


async def _push_to_viewer(app: AppContext, tool_name: str, dataset: str | None, data: dict):
    """Push a typed JSON message to the viewer if active."""
    if app.viewer is None or not app.viewer.is_active:
        return
    import json
    from datetime import datetime, timezone

    message = json.dumps({
        "type": tool_name,
        "dataset": dataset,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    })
    logger.info("Viewer push: tool=%s dataset=%s clients=%d", tool_name, dataset, app.viewer.client_count)
    await app.viewer.broadcast(message)


def _render_provenance_table(log: list, registry: DatasetRegistry) -> str:
    """Render a provenance table from the session log."""
    lines = ["## Data Sources and Queries\n"]
    lines.append("| # | Tool | Dataset | Version | Input | Output |")
    lines.append("|---|------|---------|---------|-------|--------|")

    datasets_used = {}
    for entry in log:
        idx = entry["id"]
        tool = entry["tool"]
        inputs = entry["inputs"]
        dataset = inputs.get("dataset", inputs.get("query_text", "—"))
        version_info = entry.get("dataset_version", {})
        version = version_info.get("version", "—")

        # Track datasets for citation
        ds_name = inputs.get("dataset")
        if ds_name and ds_name not in datasets_used:
            datasets_used[ds_name] = version_info

        # Summarize input
        if "sparql" in inputs:
            sparql = inputs["sparql"]
            input_summary = f"`{sparql[:60]}...`" if len(sparql) > 60 else f"`{sparql}`"
        elif "query_text" in inputs:
            input_summary = f'"{inputs["query_text"]}"'
        elif "uri" in inputs:
            input_summary = f"`{inputs['uri']}`"
        else:
            input_summary = "—"

        output_len = entry.get("output_length", 0)
        duration = entry.get("duration_ms", 0)
        output_summary = f"{output_len} chars, {duration}ms"

        lines.append(f"| {idx} | {tool} | {dataset} | {version} | {input_summary} | {output_summary} |")

    # Citations
    if datasets_used:
        lines.append("\n## Dataset Citations\n")
        for ds_name, meta in datasets_used.items():
            try:
                plugin = registry.get_plugin(ds_name)
                version = meta.get("version", "unknown")
                triples = meta.get("triple_count", "?")
                lines.append(
                    f"- **{plugin.display_name}** v{version} ({triples:,} triples). "
                    f"{plugin.license}. Cite as: {plugin.citation}"
                )
            except KeyError:
                lines.append(f"- **{ds_name}**: metadata unavailable")

    return "\n".join(lines)


def _render_markdown_report(log: list, registry: DatasetRegistry) -> str:
    """Render a full markdown report from the session log."""
    from datetime import datetime, timezone

    lines = ["# Research Session Report\n"]
    lines.append(f"**Generated:** {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"**Tool calls:** {len(log)}\n")

    # Group by tool type
    queries = [e for e in log if e["tool"] == "query"]
    searches = [e for e in log if e["tool"] == "search_entities"]
    explorations = [e for e in log if e["tool"] in ("explore_entity", "find_links", "get_provenance")]

    if queries:
        lines.append(f"## Queries ({len(queries)})\n")
        for entry in queries:
            sparql = entry["inputs"].get("sparql", "")
            dataset = entry["inputs"].get("dataset", "?")
            version_info = entry.get("dataset_version", {})
            version = version_info.get("version", "?")
            lines.append(f"### {entry['id']}: {dataset} v{version}\n")
            lines.append(f"```sparql\n{sparql}\n```\n")
            lines.append(f"**Results:** {entry.get('output_length', '?')} chars, {entry.get('duration_ms', '?')}ms\n")

    if searches:
        lines.append(f"## Entity Searches ({len(searches)})\n")
        for entry in searches:
            query_text = entry["inputs"].get("query_text", "?")
            dataset = entry["inputs"].get("dataset", "all")
            lines.append(f"- **\"{query_text}\"** in {dataset}")
        lines.append("")

    if explorations:
        lines.append(f"## Entity Explorations ({len(explorations)})\n")
        for entry in explorations:
            uri = entry["inputs"].get("uri", "?")
            lines.append(f"- `{entry['tool']}({uri})`")
        lines.append("")

    # Provenance table
    lines.append(f"\n{_render_provenance_table(log, registry)}")

    return "\n".join(lines)


def _collect_see_also(
    rows: list[dict[str, str]],
    linkage,
    max_uris: int = 50,
) -> str:
    if not linkage:
        return ""
    uris: set[str] = set()
    for row in rows:
        for value in row.values():
            if value and isinstance(value, str) and value.startswith("http"):
                uris.add(value)
            if len(uris) >= max_uris:
                break
    see_also_lines: list[str] = []
    seen_targets: set[str] = set()
    for uri in uris:
        for link in linkage.find_links(uri):
            target = link["target"]
            if target not in seen_targets:
                seen_targets.add(target)
                confidence = link.get("confidence", "")
                see_also_lines.append(f"  {uri} → {target} ({confidence})")
    if not see_also_lines:
        return ""
    return "\n─── See also ───\n" + "\n".join(see_also_lines) + "\nUse `find_links(uri)` for full provenance.\n"


def create_mcp_server() -> FastMCP:

    # Build context once, shared across all sessions.
    # NOTE: not thread-safe — update_dataset mutates stores/search on the shared
    # context. Fine for single-process MCP server; revisit if adding concurrency.
    _shared_ctx = build_app_context(skip_search=False)

    @asynccontextmanager
    async def lifespan(server: FastMCP):
        yield _shared_ctx

    mcp = FastMCP(
        "linked-past",
        instructions=(
            "Linked Past: multi-dataset prosopographical SPARQL tools. "
            "Use discover_datasets to find datasets, get_schema to learn ontologies, "
            "validate_sparql to check queries, query to execute them, "
            "search_entities to find entities across datasets, "
            "explore_entity to inspect an entity, find_links for cross-references, "
            "get_provenance for scholarly citations, and update_dataset to check freshness."
        ),
        lifespan=lifespan,
    )

    # Register viewer routes statically — they return 404 when viewer is inactive.
    from starlette.routing import Route, WebSocketRoute

    from linked_past.core.viewer import ViewerManager, set_manager, viewer_ws_handler
    from linked_past.core.viewer_api import entity_handler

    viewer_manager = ViewerManager(app_context=_shared_ctx)
    set_manager(viewer_manager)
    _shared_ctx.viewer = viewer_manager

    # Find React app dist directory
    _viewer_dist = Path(__file__).resolve().parent.parent.parent.parent / "linked-past-viewer" / "dist"

    async def _viewer_page(request):
        """Serve the React app's index.html, or error if not built."""
        from starlette.responses import HTMLResponse, PlainTextResponse

        index = _viewer_dist / "index.html"
        if not index.exists():
            return PlainTextResponse(
                "Viewer not built. Run: cd packages/linked-past-viewer && npm install && npm run build",
                status_code=404,
            )
        return HTMLResponse(index.read_text())

    async def _viewer_static(request):
        """Serve static assets from the React app's dist directory."""
        from starlette.responses import FileResponse, HTMLResponse, PlainTextResponse

        path = request.path_params.get("path", "")
        file_path = (_viewer_dist / path).resolve()
        if not str(file_path).startswith(str(_viewer_dist.resolve())):
            return PlainTextResponse("Forbidden", status_code=403)
        if not file_path.exists() or not file_path.is_file():
            # SPA fallback — return index.html for unmatched routes
            index = _viewer_dist / "index.html"
            if index.exists():
                return HTMLResponse(index.read_text())
            return PlainTextResponse("Not found", status_code=404)
        return FileResponse(file_path)

    mcp._custom_starlette_routes.extend([
        Route("/viewer/api/entity", entity_handler, methods=["GET"]),
        WebSocketRoute("/viewer/ws", viewer_ws_handler),
        Route("/viewer", _viewer_page, methods=["GET"]),
        Route("/viewer/{path:path}", _viewer_static, methods=["GET"]),
    ])

    @mcp.tool()
    def discover_datasets(ctx: Context, topic: str | None = None) -> str:
        """Discover available datasets. Without arguments, lists all loaded datasets with metadata. With a topic, uses semantic search to find relevant datasets."""
        app: AppContext = ctx.request_context.lifespan_context
        registry = app.registry

        if topic and app.search:
            results = app.search.search(topic, k=10)
            relevant_datasets = {r["dataset"] for r in results}
        else:
            relevant_datasets = None

        lines = ["# Available Datasets\n"]
        for name in registry.list_datasets():
            if relevant_datasets is not None and name not in relevant_datasets:
                continue
            plugin = registry.get_plugin(name)
            if topic and relevant_datasets is None:
                # Fallback when search index unavailable: match any topic word
                searchable = " ".join([plugin.description, plugin.display_name,
                                       plugin.spatial_coverage, plugin.time_coverage]).lower()
                topic_words = topic.lower().split()
                if not any(word in searchable for word in topic_words):
                    continue
            meta = registry.get_metadata(name)
            version = meta.get("version", "unknown")
            triple_count = meta.get("triple_count", "unknown")
            lines.append(
                f"## {plugin.display_name}\n"
                f"- **ID:** `{name}`\n"
                f"- **Period:** {plugin.time_coverage}\n"
                f"- **Geography:** {plugin.spatial_coverage}\n"
                f"- **Version:** {version}\n"
                f"- **Triples:** {triple_count}\n"
                f"- **License:** {plugin.license}\n"
                f"- **Citation:** {plugin.citation}\n"
                f"- **URL:** {plugin.url}\n"
                f"\n{plugin.description}\n"
            )
        if len(lines) == 1:
            return "No datasets match that topic." if topic else "No datasets loaded."
        return "\n".join(lines)

    @mcp.tool()
    def get_schema(ctx: Context, dataset: str) -> str:
        """Get the ontology overview for a dataset: namespace prefixes, available classes, and query tips. Call this before writing SPARQL queries."""
        app: AppContext = ctx.request_context.lifespan_context
        plugin = app.registry.get_plugin(dataset)
        return plugin.get_schema()

    @mcp.tool()
    def validate_sparql(ctx: Context, sparql: str, dataset: str) -> str:
        """Validate a SPARQL query against a dataset's schema without executing it. Checks syntax, auto-repairs missing PREFIX declarations, and validates classes and predicates."""
        app: AppContext = ctx.request_context.lifespan_context
        plugin = app.registry.get_plugin(dataset)
        prefix_map = plugin.get_prefixes()

        fixed_sparql, parse_errors = parse_and_fix_prefixes(sparql, prefix_map)
        if parse_errors:
            error_list = "\n".join(f"- {e}" for e in parse_errors)
            base = f"INVALID\n\nErrors:\n{error_list}"
            return base + plugin.get_relevant_context(sparql)

        result = plugin.validate(fixed_sparql)

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

        # Append constructive hints (non-blocking) if the validator found issues
        if result.suggestions:
            hint_list = "\n".join(f"- {h}" for h in result.suggestions)
            base += f"\n\n⚠️ Schema hints (query will still execute):\n{hint_list}"

        return base + plugin.get_relevant_context(fixed_sparql)

    @mcp.tool()
    async def query(ctx: Context, sparql: str, dataset: str, timeout: int | None = None) -> str:
        """Validate and execute a SPARQL query against a dataset's local RDF store. Returns results in tabular format with dataset citation."""
        t0 = time.monotonic()
        app: AppContext = ctx.request_context.lifespan_context
        plugin = app.registry.get_plugin(dataset)
        store = app.registry.get_store(dataset)
        prefix_map = plugin.get_prefixes()
        schema_dict = plugin.build_schema_dict()
        effective_timeout = timeout if timeout is not None else QUERY_TIMEOUT

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(validate_and_execute, sparql, store, schema_dict, prefix_map),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            return f"ERROR: Query timed out after {effective_timeout}s. Simplify the query or increase the timeout."
        except OSError as e:
            return f"ERROR: Store access error: {e}"
        except Exception as e:
            return f"ERROR: Unexpected error: {e}"

        if not result.success:
            error_list = "\n".join(f"- {e}" for e in result.errors)
            return f"ERROR:\n{error_list}"

        table = toons.dumps(result.rows)
        see_also = _collect_see_also(result.rows, app.linkage)
        meta = app.registry.get_metadata(dataset)
        version = meta.get("version", "unknown")
        footer = (
            f"\n\n─── Sources ───\n"
            f"Data: {plugin.display_name} v{version}. {plugin.license}.\n"
            f"      Cite as: {plugin.citation}\n"
            f"Tool: linked-past, https://github.com/gillisandrew/linked-past"
        )
        output = table + see_also + footer
        _log_tool_call(app, "query", {"sparql": sparql, "dataset": dataset}, output, int((time.monotonic() - t0) * 1000))
        if app.viewer and app.viewer.is_active:
            await _push_to_viewer(app, "query", dataset, {
                "rows": result.rows,
                "columns": list(result.rows[0].keys()) if result.rows else [],
                "sparql": result.sparql,
                "row_count": len(result.rows),
            })
        return output

    @mcp.tool()
    async def search_entities(ctx: Context, query_text: str, dataset: str | None = None) -> str:
        """Search entity labels across datasets. Checks meta-entities first (unified cross-dataset), then SPARQL label search per dataset."""
        t0 = time.monotonic()
        app: AppContext = ctx.request_context.lifespan_context

        # Check meta-entities first (fast, cross-dataset)
        meta_results = []
        if app.meta and not dataset:
            # 1. Substring match on canonical name + description
            meta_matches = app.meta.search(query_text, k=5)

            # 2. Full-text search (catches "the Roman general" → Pompey)
            if app.search:
                embed_hits = app.search.search(query_text, k=10, dataset="_meta")
                seen_ids = {e.id for e in meta_matches}
                for hit in embed_hits:
                    # Find the meta-entity whose description matches
                    for entity in app.meta.all_entities():
                        if entity.description == hit["text"] and entity.id not in seen_ids:
                            meta_matches.append(entity)
                            seen_ids.add(entity.id)
                            break

            for entity in meta_matches[:10]:
                meta_results.append(entity)
        registry = app.registry

        datasets_to_search = [dataset] if dataset else registry.list_datasets()
        all_results = []

        for ds_name in datasets_to_search:
            try:
                store = registry.get_store(ds_name)
            except KeyError:
                continue

            plugin = registry.get_plugin(ds_name)
            prefix_block = "\n".join(f"PREFIX {k}: <{v}>" for k, v in plugin.get_prefixes().items())

            # Build UNION branches for all label predicates (standard + dataset-specific)
            label_preds = [
                "rdfs:label",
                "skos:prefLabel",
            ]
            # Add dataset-specific name predicates from the schema
            for cls_data in (plugin._schemas.values() if hasattr(plugin, "_schemas") else []):
                for prop in cls_data.get("properties", []):
                    pred = prop["pred"]
                    if any(kw in pred.lower() for kw in ("name", "label", "title")):
                        if pred not in label_preds:
                            label_preds.append(pred)

            union_clauses = " UNION ".join(f"{{ ?uri {p} ?label }}" for p in label_preds)
            sparql = f"""
            {prefix_block}
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            SELECT DISTINCT ?uri ?label ?type WHERE {{
                {union_clauses}
                FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{query_text}")))
                OPTIONAL {{ ?uri a ?type }}
            }}
            LIMIT 20
            """
            try:
                from linked_past.core.store import execute_query as eq

                rows = eq(store, sparql)
                for row in rows:
                    all_results.append({
                        "dataset": ds_name,
                        "uri": row.get("uri", ""),
                        "label": row.get("label", ""),
                        "type": row.get("type", ""),
                    })
            except Exception as e:
                logger.warning("Search failed for %s: %s", ds_name, e)

        if not all_results and not meta_results:
            output = f"No entities found matching '{query_text}'."
            _log_tool_call(app, "search_entities", {"query_text": query_text, "dataset": dataset}, output, int((time.monotonic() - t0) * 1000))
            if app.viewer and app.viewer.is_active:
                await _push_to_viewer(app, "search", dataset, {
                    "query_text": query_text,
                    "results": [],
                })
            return output

        lines = [f"# Search Results for '{query_text}'\n"]

        # Meta-entity results first (cross-dataset unified entities)
        if meta_results:
            lines.append("## Unified Entities (cross-dataset)\n")
            for entity in meta_results:
                ds_list = ", ".join(f"{ds}({len(uris)})" for ds, uris in entity.uris.items())
                lines.append(f"- **{entity.canonical_name}**")
                if entity.date_range:
                    lines.append(f"  {entity.date_range}")
                lines.append(f"  Datasets: {ds_list}")
                if entity.wikidata_qid:
                    qid = entity.wikidata_qid.split("/")[-1]
                    lines.append(f"  Wikidata: {qid}")
                # List URIs
                for ds, uris in entity.uris.items():
                    for uri in uris[:3]:
                        lines.append(f"  - `{uri}` ({ds})")
                    if len(uris) > 3:
                        lines.append(f"  - ... and {len(uris) - 3} more in {ds}")
                lines.append("")

        # Per-dataset SPARQL results
        by_dataset: dict[str, list] = {}
        for r in all_results:
            by_dataset.setdefault(r["dataset"], []).append(r)

        if by_dataset:
            lines.append("## Per-Dataset Results\n")
        for ds_name, results in by_dataset.items():
            plugin = registry.get_plugin(ds_name)
            lines.append(f"## {plugin.display_name}\n")
            for r in results[:10]:
                type_str = f" ({r['type'].rsplit('/', 1)[-1].rsplit('#', 1)[-1]})" if r["type"] else ""
                lines.append(f"- **{r['label']}**{type_str}\n  `{r['uri']}`")
            if len(results) > 10:
                lines.append(f"  ... and {len(results) - 10} more")
            lines.append("")

        output = "\n".join(lines)
        _log_tool_call(app, "search_entities", {"query_text": query_text, "dataset": dataset}, output, int((time.monotonic() - t0) * 1000))
        if app.viewer and app.viewer.is_active:
            await _push_to_viewer(app, "search", dataset, {
                "query_text": query_text,
                "results": all_results,
            })
        return output

    @mcp.tool()
    async def explore_entity(ctx: Context, uri: str) -> str:
        """Explore an entity across datasets. Returns properties from its home dataset, cross-links from the linkage graph, and suggested next steps."""
        t0 = time.monotonic()
        app: AppContext = ctx.request_context.lifespan_context
        registry = app.registry

        ds_name = registry.dataset_for_uri(uri)
        lines = [f"# Entity: `{uri}`\n"]

        # Check if this URI belongs to a meta-entity
        if app.meta:
            meta_entity = app.meta.get_by_uri(uri)
            if meta_entity:
                lines.append(f"**Unified Entity:** {meta_entity.canonical_name}")
                if meta_entity.date_range:
                    lines.append(f"**Period:** {meta_entity.date_range}")
                ds_list = ", ".join(f"{ds}({len(uris)})" for ds, uris in meta_entity.uris.items())
                lines.append(f"**Also in:** {ds_list}")
                if meta_entity.wikidata_qid:
                    lines.append(f"**Wikidata:** {meta_entity.wikidata_qid.split('/')[-1]}")
                lines.append("")

        rows = []
        if ds_name:
            plugin = registry.get_plugin(ds_name)
            lines.append(f"**Dataset:** {plugin.display_name}\n")

            try:
                store = registry.get_store(ds_name)
                sparql = f"SELECT ?pred ?obj WHERE {{ <{uri}> ?pred ?obj . }} LIMIT 50"
                from linked_past.core.store import execute_query as eq

                rows = eq(store, sparql)
                if rows:
                    lines.append("## Properties\n")
                    for row in rows:
                        pred = row["pred"].rsplit("/", 1)[-1].rsplit("#", 1)[-1]
                        obj = row["obj"] or ""
                        if len(obj) > 100:
                            obj = obj[:100] + "..."
                        lines.append(f"- **{pred}:** {obj}")
                    lines.append("")
            except Exception as e:
                lines.append(f"Error querying {ds_name}: {e}\n")
        else:
            lines.append("**Dataset:** Unknown (URI namespace not recognized)\n")

        # Cross-dataset links: curated linkage graph + in-data SKOS/OWL xrefs
        linkage_links = app.linkage.find_links(uri) if app.linkage else []
        store_links = _find_store_xrefs(uri, app.registry)
        seen = set()
        xrefs = []
        for link in linkage_links + store_links:
            if link["target"] not in seen:
                seen.add(link["target"])
                xrefs.append(link)
        if xrefs:
            lines.append("## Cross-Dataset Links\n")
            for link in xrefs:
                lines.append(
                    f"- **{link['relationship']}** → `{link['target']}`\n"
                    f"  {link.get('confidence', '')} | {link['basis']}"
                )
            lines.append("")

        lines.append("## Suggested Next Steps\n")
        if ds_name == "dprr":
            lines.append("- Query DPRR for office-holdings: `query(sparql, 'dprr')` with PostAssertion joins")
            lines.append("- Check family relationships via RelationshipAssertion")
        elif ds_name == "pleiades":
            lines.append("- Get coordinates via `pleiades:hasLocation`")
            lines.append("- Find ancient names via `pleiades:hasName`")
        last_segment = uri.rsplit("/", 1)[-1]
        lines.append(f"- Search for related entities: `search_entities('{last_segment}')`")
        lines.append(f"- Find cross-dataset links: `find_links('{uri}')`")

        output = "\n".join(lines)
        _log_tool_call(app, "explore_entity", {"uri": uri}, output, int((time.monotonic() - t0) * 1000))
        if app.viewer and app.viewer.is_active:
            name = uri.rsplit("/", 1)[-1]
            for pred in ("hasPersonName", "label", "prefLabel", "rdfs:label", "title", "name"):
                for row in rows:
                    if row["pred"].rsplit("/", 1)[-1].rsplit("#", 1)[-1] == pred:
                        name = row["obj"]
                        break
                if name != uri.rsplit("/", 1)[-1]:
                    break
            await _push_to_viewer(app, "entity", ds_name, {
                "uri": uri,
                "name": name,
                "properties": [{"pred": r["pred"], "obj": r["obj"] or ""} for r in rows],
                "xrefs": xrefs,
            })
        return output

    @mcp.tool()
    async def find_links(ctx: Context, uri: str) -> str:
        """Find all cross-dataset links for an entity. Checks both the curated linkage graph AND the dataset stores for SKOS/OWL cross-reference predicates (closeMatch, exactMatch, sameAs)."""
        t0 = time.monotonic()
        app: AppContext = ctx.request_context.lifespan_context
        ds_name = app.registry.dataset_for_uri(uri)

        # Collect from curated linkage graph
        linkage_links = app.linkage.find_links(uri) if app.linkage else []

        # Collect from dataset stores (SKOS/OWL predicates already in the RDF)
        store_links = _find_store_xrefs(uri, app.registry)

        # Deduplicate by target URI
        seen_targets = set()
        all_links = []
        for link in linkage_links + store_links:
            if link["target"] not in seen_targets:
                seen_targets.add(link["target"])
                all_links.append(link)

        if not all_links:
            other_datasets = [n for n in app.registry.list_datasets() if n != ds_name]
            return (
                f"No links found for `{uri}`.\n\n"
                f"Try searching other datasets: {', '.join(other_datasets)}\n"
                f"Use `search_entities()` to find potential matches."
            )

        # Group by confidence/source
        by_confidence: dict[str, list] = {}
        for link in all_links:
            by_confidence.setdefault(link["confidence"], []).append(link)

        lines = [f"# Links for `{uri}`\n"]
        for level in ["confirmed", "probable", "concordance", "in-data", "candidate"]:
            group = by_confidence.get(level, [])
            if group:
                label = "In Dataset" if level == "in-data" else level.title()
                lines.append(f"## {label} ({len(group)})\n")
                for link in group:
                    lines.append(
                        f"- **{link['relationship']}** → `{link['target']}`\n"
                        f"  {link['basis']}"
                    )
                lines.append("")

        output = "\n".join(lines)
        _log_tool_call(app, "find_links", {"uri": uri}, output, int((time.monotonic() - t0) * 1000))
        if app.viewer and app.viewer.is_active:
            await _push_to_viewer(app, "links", ds_name, {
                "uri": uri,
                "links": [
                    {"target": lnk["target"], "relationship": lnk.get("relationship", ""),
                     "confidence": lnk.get("confidence", ""), "basis": lnk.get("basis", "")}
                    for lnk in linkage_links + store_links
                ],
            })
        return output

    @mcp.tool()
    def get_provenance(ctx: Context, uri: str, predicate: str | None = None) -> str:
        """Get full provenance for an entity or a specific claim. Returns source, factoid, dataset chain plus linkage basis for cross-references."""
        app: AppContext = ctx.request_context.lifespan_context
        registry = app.registry

        ds_name = registry.dataset_for_uri(uri)
        lines = [f"# Provenance for `{uri}`\n"]

        if ds_name:
            plugin = registry.get_plugin(ds_name)
            meta = registry.get_metadata(ds_name)

            lines.append(f"## Dataset: {plugin.display_name}\n")
            lines.append(f"- **Version:** {meta.get('version', 'unknown')}")
            lines.append(f"- **License:** {plugin.license}")
            lines.append(f"- **Citation:** {plugin.citation}")
            lines.append(f"- **URL:** {plugin.url}")

            # Include VoID stats if available
            void_meta = meta.get("void", {})
            if void_meta:
                lines.append(f"- **Triples:** {int(void_meta['triples']):,}" if "triples" in void_meta else "")
                lines.append(f"- **Entities:** {int(void_meta['entities']):,}" if "entities" in void_meta else "")
                lines.append(f"- **Classes:** {void_meta['classes']}" if "classes" in void_meta else "")
                lines.append(f"- **Properties:** {void_meta['properties']}" if "properties" in void_meta else "")
                lines = [line for line in lines if line]  # remove empty strings
                if "classPartitions" in void_meta:
                    lines.append("\n### Class Partitions\n")
                    for cp in void_meta["classPartitions"]:
                        cls_name = cp["class"].rsplit("#", 1)[-1].rsplit("/", 1)[-1]
                        lines.append(f"- **{cls_name}:** {int(cp['entities']):,} instances")

            lines.append("")

            try:
                store = registry.get_store(ds_name)
                from linked_past.core.store import execute_query as eq

                if predicate:
                    sparql = f"SELECT ?obj WHERE {{ <{uri}> <{predicate}> ?obj . }}"
                else:
                    sparql = f"SELECT ?pred ?obj WHERE {{ <{uri}> ?pred ?obj . }} LIMIT 50"
                rows = eq(store, sparql)
                if rows:
                    lines.append("## Assertions\n")
                    for row in rows:
                        if predicate:
                            lines.append(f"- {row['obj']}")
                        else:
                            pred_short = row["pred"].rsplit("/", 1)[-1].rsplit("#", 1)[-1]
                            lines.append(f"- **{pred_short}:** {row['obj'] or ''}")
                    lines.append("")
            except Exception as e:
                lines.append(f"Error: {e}\n")

            # DPRR-specific: secondary sources
            if ds_name == "dprr":
                try:
                    store = registry.get_store(ds_name)
                    source_sparql = f"""
                    PREFIX vocab: <http://romanrepublic.ac.uk/rdf/ontology#>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    SELECT ?source ?sourceLabel WHERE {{
                        ?assertion vocab:isAboutPerson <{uri}> ;
                                   vocab:hasSecondarySource ?source .
                        ?source rdfs:label ?sourceLabel .
                    }}
                    """
                    rows = eq(store, source_sparql)
                    if rows:
                        lines.append("## Secondary Sources\n")
                        seen: set[str] = set()
                        for row in rows:
                            label = row.get("sourceLabel", "")
                            if label and label not in seen:
                                lines.append(f"- {label}")
                                seen.add(label)
                        lines.append("")
                except Exception:
                    pass

        if app.linkage:
            links = app.linkage.find_links(uri)
            if links:
                lines.append("## Cross-Reference Provenance\n")
                for link in links:
                    prov = app.linkage.get_provenance(uri, link["target"])
                    if prov:
                        lines.append(
                            f"- **{link['relationship']}** → `{link['target']}`\n"
                            f"  Basis: {prov.get('basis', 'unknown')}\n"
                            f"  Confidence: {prov.get('confidence', 'unknown')}\n"
                            f"  Method: {prov.get('method', 'unknown')}\n"
                            f"  Attributed to: {prov.get('author', 'unknown')}"
                        )
                lines.append("")

        return "\n".join(lines)

    @mcp.tool()
    def update_dataset(ctx: Context, dataset: str | None = None, force: bool = False) -> str:
        """Check status, initialize unloaded datasets, or force re-download. If a dataset is registered but not yet initialized (no local data), this will download and load it. Use force=True to re-pull from the registry even if already initialized."""
        app: AppContext = ctx.request_context.lifespan_context
        registry = app.registry

        datasets_to_check = [dataset] if dataset else registry.list_datasets()
        lines = ["# Dataset Status\n"]

        for ds_name in datasets_to_check:
            try:
                plugin = registry.get_plugin(ds_name)
            except KeyError:
                lines.append(f"## {ds_name}\n- **Error:** Unknown dataset\n")
                continue

            # Check if initialized
            try:
                registry.get_store(ds_name)
                initialized = True
            except KeyError:
                initialized = False

            # Force re-download: delete store so it gets rebuilt
            if force and initialized:
                import shutil

                dataset_dir = registry._data_dir / ds_name
                store_path = dataset_dir / "store"
                if store_path.exists():
                    # Close existing store first
                    if ds_name in registry._stores:
                        del registry._stores[ds_name]
                    shutil.rmtree(store_path)
                initialized = False
                lines.append(f"## {plugin.display_name}\n")
                lines.append("- **Force update:** deleted local store, re-downloading...")

            if not initialized:
                lines.append(f"## {plugin.display_name}\n")
                lines.append("- **Status:** Not initialized — downloading from OCI...")
                try:
                    registry.initialize_dataset(ds_name)
                    meta = registry.get_metadata(ds_name)
                    lines.append(f"- **Initialized:** {meta.get('triple_count', '?')} triples loaded")
                    lines.append(f"- **Version:** {meta.get('version', 'unknown')}")

                    # Hot-reload: rebuild search index for this dataset
                    if app.search:
                        app.search.clear_dataset(ds_name)
                        try:
                            store = registry.get_store(ds_name)
                        except KeyError:
                            store = None
                        _index_dataset(app.search, ds_name, plugin, store)
                        lines.append("- **Search index:** rebuilt")
                except Exception as e:
                    lines.append(f"- **Error:** {e}")
                lines.append("")
                continue

            meta = registry.get_metadata(ds_name)
            version = meta.get("version", "unknown")
            triple_count = meta.get("triple_count", "unknown")

            update_info = plugin.check_for_updates()

            lines.append(f"## {plugin.display_name}\n")
            lines.append(f"- **Current version:** {version}")
            lines.append(f"- **Triples:** {triple_count}")
            lines.append(f"- **OCI artifact:** {plugin.oci_dataset}:{plugin.oci_version}")

            if update_info:
                lines.append(f"- **Available:** {update_info.available}")
                if update_info.changelog_url:
                    lines.append(f"- **Changelog:** {update_info.changelog_url}")
                lines.append("\nTo update, re-initialize with a fresh data directory.")
            else:
                lines.append("- **Status:** Up to date (or no update check available)")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool()
    def export_report(ctx: Context, format: str = "markdown", path: str | None = None) -> str:
        """Export the current session's queries and results as a report. Formats: 'json' (raw log), 'provenance' (methods table), 'markdown' (full report)."""
        app: AppContext = ctx.request_context.lifespan_context

        if not app.session_log:
            return "No tool calls recorded in this session yet."

        if format == "json":
            import json as json_mod

            content = json_mod.dumps(app.session_log, indent=2, default=str)
        elif format == "provenance":
            content = _render_provenance_table(app.session_log, app.registry)
        else:
            content = _render_markdown_report(app.session_log, app.registry)

        if path:
            Path(path).write_text(content)
            return f"Report ({format}) written to {path} ({len(app.session_log)} entries)"
        return content

    @mcp.tool()
    def disambiguate(
        ctx: Context,
        uri: str | None = None,
        name: str | None = None,
        filiation: str | None = None,
        office: str | None = None,
        date: int | None = None,
        province: str | None = None,
    ) -> str:
        """Disambiguate a Roman person against DPRR candidates using filiation, career, geography, and temporal signals.

        Provide either a DPRR/EDH person URI (to extract context automatically) or a name
        with optional supporting fields. Returns a ranked list of DPRR candidates with
        per-signal scores and a confidence classification.

        Args:
            uri: EDH person URI to extract context from (overrides name if no name given).
            name: Person name (Latin or Greek). Required if uri not provided.
            filiation: Filiation string, e.g. "M. f. M. n." (father/grandfather abbreviations).
            office: Office held, e.g. "cos.", "q.", "pr." (abbreviated or full).
            date: Date of activity (negative = BC), e.g. -129 for 129 BCE.
            province: Province name or Pleiades URI for the inscription findspot.
        """
        from linked_past.core.disambiguate import (
            WEIGHTS,
            PersonDisambiguator,
            SignalResult,
            extract_context_from_edh_uri,
            extract_context_from_fields,
            fetch_dprr_candidates,
            fetch_dprr_family,
            fetch_dprr_offices,
            fetch_dprr_province_pleiades,
            score_career,
            score_filiation,
            score_geography,
            score_temporal,
        )
        from linked_past.core.onomastics import parse_filiation

        app: AppContext = ctx.request_context.lifespan_context

        # ── Build PersonContext ──────────────────────────────────────────────
        person_ctx = None

        if uri and not name:
            try:
                edh_store = app.registry.get_store("edh")
                person_ctx = extract_context_from_edh_uri(uri, edh_store)
            except KeyError:
                return "ERROR: EDH dataset is not loaded. Run `update_dataset('edh')` first."
            if person_ctx is None:
                return f"ERROR: No EDH person found at `{uri}`."
        else:
            if not name:
                return "ERROR: Provide either `uri` or `name`."
            person_ctx = extract_context_from_fields(
                name=name,
                filiation=filiation,
                office=office,
                date=date,
                province=province,
                uri=uri,
            )

        if person_ctx.nomen is None:
            return (
                f"ERROR: Could not parse a nomen from '{person_ctx.name}'. "
                "Provide a full Roman name (e.g. 'L. Aquillius Florus')."
            )

        # ── Fetch DPRR candidates ────────────────────────────────────────────
        try:
            dprr_store = app.registry.get_store("dprr")
        except KeyError:
            return "ERROR: DPRR dataset is not loaded. Run `update_dataset('dprr')` first."

        candidates = fetch_dprr_candidates(dprr_store, person_ctx.nomen)
        if not candidates:
            return (
                f"No DPRR candidates found for nomen **{person_ctx.nomen}**.\n\n"
                "Try `search_entities()` with the nomen to check spelling."
            )

        # ── Parse inscription filiation ──────────────────────────────────────
        inscription_filiation: dict[str, str] = {}
        if person_ctx.filiation:
            inscription_filiation = parse_filiation(person_ctx.filiation)

        # ── Score each candidate ─────────────────────────────────────────────
        disambiguator = PersonDisambiguator()
        candidates_signals = []

        for cand in candidates:
            cand_uri = cand.get("person", "")
            cand_label = cand.get("label", cand_uri)
            era_from_raw = cand.get("eraFrom")
            era_to_raw = cand.get("eraTo")
            try:
                era_from = int(era_from_raw) if era_from_raw else None
            except (ValueError, TypeError):
                era_from = None
            try:
                era_to = int(era_to_raw) if era_to_raw else None
            except (ValueError, TypeError):
                era_to = None

            # Fetch supporting data for this candidate
            dprr_offices = fetch_dprr_offices(dprr_store, cand_uri)
            dprr_family = fetch_dprr_family(dprr_store, cand_uri)
            province_pleiades = fetch_dprr_province_pleiades(dprr_store, app.linkage, cand_uri)

            # Compute signals
            t_score, t_expl, t_absent = score_temporal(
                era_from, era_to,
                person_ctx.date_start, person_ctx.date_end,
            )
            c_score, c_expl, c_absent = score_career(
                dprr_offices, era_from,
                person_ctx.office, person_ctx.date_start,
            )
            f_score, f_expl, f_absent = score_filiation(dprr_family, inscription_filiation)
            g_score, g_expl, g_absent = score_geography(
                province_pleiades, person_ctx.findspot_uri,
            )

            signals = {
                "filiation": SignalResult(f_score, WEIGHTS["filiation"], f_expl, f_absent),
                "career":    SignalResult(c_score, WEIGHTS["career"],    c_expl, c_absent),
                "geography": SignalResult(g_score, WEIGHTS["geography"], g_expl, g_absent),
                "temporal":  SignalResult(t_score, WEIGHTS["temporal"],  t_expl, t_absent),
            }
            candidates_signals.append((cand_uri, cand_label, signals))

        ranked = disambiguator.rank_candidates(candidates_signals)

        # ── Format output ────────────────────────────────────────────────────
        conf_icons = {"strong": "✓✓", "probable": "✓", "ambiguous": "?"}
        lines = [
            f"# Disambiguation: {person_ctx.name}\n",
            f"**Nomen searched:** {person_ctx.nomen}  ",
            f"**Praenomen:** {person_ctx.praenomen or '(unknown)'}  ",
            f"**Office:** {person_ctx.office or '(none)'}  ",
            f"**Date:** {person_ctx.date_start or '(none)'}  ",
            f"**Filiation parsed:** {inscription_filiation or '(none)'}",
            "",
            f"Found **{len(ranked)}** candidate(s).\n",
        ]

        for i, match in enumerate(ranked, 1):
            icon = conf_icons.get(match.confidence, "?")
            lines.append(
                f"## {i}. {icon} [{match.confidence.upper()}] score={match.score:.3f}"
            )
            lines.append(f"**URI:** `{match.dprr_uri}`")
            lines.append(f"**Label:** {match.dprr_label}")
            lines.append("")
            lines.append("| Signal | Score | Weight | Note |")
            lines.append("|--------|-------|--------|------|")
            for sig_name, sig in match.signals.items():
                absent_flag = " (absent)" if sig.is_absent else ""
                lines.append(
                    f"| {sig_name} | {sig.score:.2f}{absent_flag} | {sig.weight:.2f} | {sig.explanation} |"
                )
            lines.append("")

        if ranked:
            top = ranked[0]
            lines.append("---")
            lines.append(f"**Best match:** `{top.dprr_uri}` — {top.dprr_label}")
            lines.append(
                f"**Confidence:** {top.confidence} (score {top.score:.3f})"
            )
            lines.append(
                "Use `explore_entity(uri)` for full DPRR record or "
                "`find_links(uri)` for cross-references."
            )

        return "\n".join(lines)

    @mcp.tool()
    def analyze_question(ctx: Context, question: str) -> str:
        """Analyze a natural language question to determine which datasets, entities, and concepts are relevant. Call this before writing SPARQL to get targeted guidance."""
        app: AppContext = ctx.request_context.lifespan_context
        from linked_past.core.extraction import extract_question

        available = [n for n in app.registry.list_datasets() if n in app.registry._stores]
        extraction = extract_question(question, available)

        lines = ["# Question Analysis\n"]
        lines.append(f"**Intent:** {extraction.intent}")
        if extraction.entities:
            lines.append(f"**Entities:** {', '.join(extraction.entities)}")
        if extraction.classes:
            lines.append(f"**Concepts:** {', '.join(extraction.classes)}")
        if extraction.temporal:
            lines.append(f"**Temporal:** {extraction.temporal}")
        if extraction.spatial:
            lines.append(f"**Spatial:** {extraction.spatial}")
        if extraction.steps:
            lines.append("**Steps:**")
            for i, step in enumerate(extraction.steps, 1):
                lines.append(f"  {i}. {step}")
        lines.append(f"\n**Suggested datasets:** {', '.join(extraction.suggested_datasets)}")

        # Get relevant schemas for suggested datasets
        lines.append("\n## Relevant Schemas\n")
        for ds_name in extraction.suggested_datasets:
            try:
                plugin = app.registry.get_plugin(ds_name)
                lines.append(f"### {plugin.display_name}\n")
                # Get relevant context using extraction terms
                search_terms = " ".join(extraction.entities + extraction.classes)
                if search_terms and hasattr(plugin, "get_relevant_context"):
                    ctx_text = plugin.get_relevant_context(
                        "SELECT ?x WHERE { ?x a ?type }"  # Dummy SPARQL to trigger context
                    )
                    if ctx_text:
                        lines.append(ctx_text)
            except KeyError:
                pass

        return "\n".join(lines)

    @mcp.tool()
    async def start_viewer(ctx: Context) -> str:
        """Start the browser-based result viewer. Opens a live feed of query results, entity cards, and cross-references at a URL you can open in your browser."""
        app: AppContext = ctx.request_context.lifespan_context

        if app.viewer is not None and app.viewer.is_active:
            port = mcp.settings.port or 8000
            url = app.viewer.viewer_url("localhost", port)
            return f"Viewer already running at {url}"

        app.viewer.activate()
        port = mcp.settings.port or 8000
        url = app.viewer.viewer_url("localhost", port)
        return (
            f"Viewer started at {url}\n\n"
            "Query results, entity cards, and cross-references will now appear in the viewer automatically. "
            "You can also use `push_to_viewer(content)` to send markdown reports, summaries, or analysis directly to the viewer."
        )

    @mcp.tool()
    async def stop_viewer(ctx: Context) -> str:
        """Stop the browser-based result viewer."""
        app: AppContext = ctx.request_context.lifespan_context

        if app.viewer is None or not app.viewer.is_active:
            return "Viewer is not running."

        await app.viewer.deactivate()
        return "Viewer stopped."

    @mcp.tool()
    async def push_to_viewer(ctx: Context, content: str, title: str | None = None) -> str:
        """Push markdown content to the browser viewer as a styled report. Renders headings, tables, lists, code blocks, bold, and italic. Use this to send formatted analysis, summaries, or comparisons to the viewer for the user to read alongside the conversation."""
        app: AppContext = ctx.request_context.lifespan_context

        if app.viewer is None or not app.viewer.is_active:
            return "Viewer is not running. Call start_viewer() first."

        await _push_to_viewer(app, "report", None, {
            "title": title,
            "markdown": content,
        })
        return f"Pushed to viewer{f': {title}' if title else ''}."

    return mcp


def _cmd_serve(args):
    """Start the MCP server."""
    mcp = create_mcp_server()
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")


def _cmd_init(args):
    """Download and initialize selected datasets."""
    import sys

    data_dir = get_data_dir()
    registry = DatasetRegistry(data_dir=data_dir)

    # Register all plugins
    registry.register(DPRRPlugin())
    registry.register(PleiadesPlugin())
    registry.register(PeriodOPlugin())
    registry.register(NomismaPlugin())
    registry.register(CRROPlugin())
    registry.register(OCREPlugin())
    registry.register(EDHPlugin())

    available = registry.list_datasets()

    if args.datasets:
        selected = args.datasets
        invalid = [d for d in selected if d not in available]
        if invalid:
            print(f"Unknown datasets: {', '.join(invalid)}")
            print(f"Available: {', '.join(available)}")
            sys.exit(1)
    elif args.all:
        selected = available
    else:
        # Interactive selection
        print("Available datasets:\n")
        for i, name in enumerate(available, 1):
            plugin = registry.get_plugin(name)
            from linked_past.core.store import is_initialized

            store_path = data_dir / name / "store"
            status = "installed" if is_initialized(store_path) else "not installed"
            print(f"  {i}. {name:12s} {plugin.display_name} [{status}]")
        print(f"\n  Data directory: {data_dir}")
        print("\nEnter dataset names (space-separated), 'all', or Ctrl+C to cancel:")
        try:
            choice = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            return
        if choice == "all":
            selected = available
        else:
            selected = choice.split()

    for name in selected:
        plugin = registry.get_plugin(name)
        print(f"\n{'=' * 60}")
        print(f"Initializing {plugin.display_name}...")
        print(f"{'=' * 60}")
        try:
            registry.initialize_dataset(name)
            meta = registry.get_metadata(name)
            print(f"  Done: {meta.get('triple_count', '?'):,} triples loaded")
        except Exception as e:
            print(f"  Error: {e}")

    print(f"\nDatasets stored in {data_dir}")
    print("Start the server with: linked-past-server")


def _cmd_status(args):
    """Show status of all datasets."""
    data_dir = get_data_dir()
    registry = DatasetRegistry(data_dir=data_dir)

    registry.register(DPRRPlugin())
    registry.register(PleiadesPlugin())
    registry.register(PeriodOPlugin())
    registry.register(NomismaPlugin())
    registry.register(CRROPlugin())
    registry.register(OCREPlugin())
    registry.register(EDHPlugin())

    print(f"Data directory: {data_dir}\n")
    print(f"{'Dataset':12s} {'Status':14s} {'Triples':>10s}  {'Display Name'}")
    print("-" * 70)

    for name in registry.list_datasets():
        plugin = registry.get_plugin(name)
        from linked_past.core.store import is_initialized

        store_path = data_dir / name / "store"
        if is_initialized(store_path):
            # Load metadata
            registry.initialize_dataset(name)
            meta = registry.get_metadata(name)
            triples = f"{meta.get('triple_count', '?'):,}"
            status = "installed"
        else:
            triples = "-"
            status = "not installed"
        print(f"{name:12s} {status:14s} {triples:>10s}  {plugin.display_name}")


def _cmd_rebuild(args):
    """Clear and rebuild search index + meta-entity caches."""
    data_dir = get_data_dir()

    for db_name in ["search.db", "embeddings.db", "meta_entities.db"]:
        db_path = data_dir / db_name
        if db_path.exists():
            db_path.unlink()
            print(f"Cleared {db_name}")

    print("\nRebuilding...")
    ctx = build_app_context(eager=False, skip_search=False)
    search_count = 0
    meta_count = 0
    if ctx.search:
        search_count = ctx.search._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    if ctx.meta:
        meta_count = len(ctx.meta.all_entities())
    print(f"Done: {search_count} search documents, {meta_count} meta-entities")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="linked-past-server",
        description="Linked Past — multi-dataset prosopographical SPARQL tools",
    )
    sub = parser.add_subparsers(dest="command")

    # Default: serve (no subcommand = start server)
    serve = sub.add_parser("serve", help="Start the MCP server (default)")
    serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    serve.set_defaults(func=_cmd_serve)

    # init: download datasets
    init = sub.add_parser("init", help="Download and initialize datasets")
    init.add_argument("datasets", nargs="*", help="Dataset names to initialize (e.g., dprr pleiades)")
    init.add_argument("--all", action="store_true", help="Initialize all datasets")
    init.set_defaults(func=_cmd_init)

    # status: show what's installed
    status = sub.add_parser("status", help="Show dataset installation status")
    status.set_defaults(func=_cmd_status)

    # rebuild: clear caches and rebuild search index/meta-entities
    rebuild = sub.add_parser("rebuild", help="Clear and rebuild embedding + meta-entity caches")
    rebuild.set_defaults(func=_cmd_rebuild)

    # Also support bare --host/--port for backward compat (no subcommand = serve)
    parser.add_argument("--host", default="127.0.0.1", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=8000, help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.command is None:
        # No subcommand = start server (backward compat)
        _cmd_serve(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
