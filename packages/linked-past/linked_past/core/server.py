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

from linked_past.core.embeddings import EmbeddingIndex
from linked_past.core.linkage import LinkageGraph
from linked_past.core.registry import DatasetRegistry
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
    embeddings: EmbeddingIndex | None = None
    meta: object = None  # MetaEntityIndex
    session_log: list = None

    def __post_init__(self):
        if self.session_log is None:
            self.session_log = []


def _build_embeddings(registry: DatasetRegistry, data_dir: Path) -> EmbeddingIndex | None:
    """Load or build embedding index from plugin context. Skips rebuild if DB is populated."""
    try:
        embeddings_path = data_dir / "embeddings.db"
        embeddings = EmbeddingIndex(embeddings_path)

        # Check if already populated — skip expensive rebuild
        existing = embeddings._conn.execute("SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL").fetchone()[0]
        if existing > 0:
            logger.info("Embedding index loaded from cache (%d documents)", existing)
            return embeddings

        # First time — build from scratch
        logger.info("Building embedding index (first time)...")
        for name in registry.list_datasets():
            plugin = registry.get_plugin(name)
            embeddings.add(name, "dataset", f"{plugin.display_name}: {plugin.description}")
            if hasattr(plugin, "_examples"):
                for ex in plugin._examples:
                    embeddings.add(name, "example", f"{ex['question']}\n{ex['sparql']}")
            if hasattr(plugin, "_tips"):
                for tip in plugin._tips:
                    embeddings.add(name, "tip", f"{tip['title']}: {tip['body']}")
            if hasattr(plugin, "_schemas"):
                for cls_name, cls_data in plugin._schemas.items():
                    embeddings.add(name, "schema", f"{cls_name}: {cls_data.get('comment', '')}")

        embeddings.build()
        logger.info("Embedding index built and cached")
        return embeddings
    except Exception as e:
        logger.warning("Failed to build embedding index: %s", e)
        return None


def build_app_context(*, eager: bool = False) -> AppContext:
    """Register plugins and return context.

    Args:
        eager: If True, initialize all datasets (may download). If False (default),
               only open datasets already cached locally.
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

    embeddings = _build_embeddings(registry, data_dir)

    # Build meta-entity index (skip if already cached)
    meta = None
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
            if embeddings and count > 0:
                for entity in meta.all_entities():
                    embeddings.add("_meta", "meta_entity", entity.description)
                embeddings.build()
    except Exception as e:
        logger.warning("Failed to build meta-entities: %s", e)

    return AppContext(registry=registry, linkage=linkage, embeddings=embeddings, meta=meta)


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

    @asynccontextmanager
    async def lifespan(server: FastMCP):
        ctx = build_app_context()
        yield ctx

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

    @mcp.tool()
    def discover_datasets(ctx: Context, topic: str | None = None) -> str:
        """Discover available datasets. Without arguments, lists all loaded datasets with metadata. With a topic, uses semantic search to find relevant datasets."""
        app: AppContext = ctx.request_context.lifespan_context
        registry = app.registry

        if topic and app.embeddings:
            results = app.embeddings.search(topic, k=10)
            relevant_datasets = {r["dataset"] for r in results}
        else:
            relevant_datasets = None

        lines = ["# Available Datasets\n"]
        for name in registry.list_datasets():
            if relevant_datasets is not None and name not in relevant_datasets:
                continue
            plugin = registry.get_plugin(name)
            if topic and relevant_datasets is None:
                searchable = [plugin.description, plugin.display_name,
                              plugin.spatial_coverage, plugin.time_coverage]
                if not any(topic.lower() in field.lower() for field in searchable):
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
        if not result.valid:
            error_list = "\n".join(f"- {e}" for e in result.errors)
            base = f"INVALID\n\nErrors:\n{error_list}"
            return base + plugin.get_relevant_context(fixed_sparql)

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
        return output

    @mcp.tool()
    def search_entities(ctx: Context, query_text: str, dataset: str | None = None) -> str:
        """Search entity labels across datasets. Checks meta-entities first (unified cross-dataset), then SPARQL label search per dataset."""
        t0 = time.monotonic()
        app: AppContext = ctx.request_context.lifespan_context

        # Check meta-entities first (fast, cross-dataset)
        meta_results = []
        if app.meta and not dataset:
            # 1. Substring match on canonical name + description
            meta_matches = app.meta.search(query_text, k=5)

            # 2. Semantic search via embeddings (catches "the Roman general" → Pompey)
            if app.embeddings:
                embed_hits = app.embeddings.search(query_text, k=10, dataset="_meta")
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
        return output

    @mcp.tool()
    def explore_entity(ctx: Context, uri: str) -> str:
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
        return output

    @mcp.tool()
    def find_links(ctx: Context, uri: str) -> str:
        """Find all cross-dataset links for an entity. Checks both the curated linkage graph AND the dataset stores for SKOS/OWL cross-reference predicates (closeMatch, exactMatch, sameAs)."""
        t0 = time.monotonic()
        app: AppContext = ctx.request_context.lifespan_context

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
            ds_name = app.registry.dataset_for_uri(uri)
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
        for level in ["confirmed", "probable", "in-data", "candidate"]:
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
            lines.append(f"- **URL:** {plugin.url}\n")

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
    def update_dataset(ctx: Context, dataset: str | None = None) -> str:
        """Check status, initialize unloaded datasets, or check for updates. If a dataset is registered but not yet initialized (no local data), this will download and load it."""
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

            if not initialized:
                lines.append(f"## {plugin.display_name}\n")
                lines.append("- **Status:** Not initialized — downloading from OCI...")
                try:
                    registry.initialize_dataset(ds_name)
                    meta = registry.get_metadata(ds_name)
                    lines.append(f"- **Initialized:** {meta.get('triple_count', '?')} triples loaded")
                    lines.append(f"- **Version:** {meta.get('version', 'unknown')}")

                    # Hot-reload: add new dataset to embedding index
                    if app.embeddings:
                        app.embeddings.add(ds_name, "dataset", f"{plugin.display_name}: {plugin.description}")
                        if hasattr(plugin, "_examples"):
                            for ex in plugin._examples:
                                app.embeddings.add(ds_name, "example", f"{ex['question']}\n{ex['sparql']}")
                        if hasattr(plugin, "_tips"):
                            for tip in plugin._tips:
                                app.embeddings.add(ds_name, "tip", f"{tip['title']}: {tip['body']}")
                        if hasattr(plugin, "_schemas"):
                            for cls_name, cls_data in plugin._schemas.items():
                                app.embeddings.add(ds_name, "schema", f"{cls_name}: {cls_data.get('comment', '')}")
                        app.embeddings.build()
                        lines.append("- **Embeddings:** rebuilt")
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
    """Clear and rebuild embedding + meta-entity caches."""
    data_dir = get_data_dir()

    for db_name in ["embeddings.db", "meta_entities.db"]:
        db_path = data_dir / db_name
        if db_path.exists():
            db_path.unlink()
            print(f"Cleared {db_name}")
        else:
            print(f"{db_name} not found (nothing to clear)")

    print("\nRebuilding (this may take 30-60s for embeddings)...")
    ctx = build_app_context(eager=False)
    embed_count = 0
    meta_count = 0
    if ctx.embeddings:
        embed_count = ctx.embeddings._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    if ctx.meta:
        meta_count = len(ctx.meta.all_entities())
    print(f"Done: {embed_count} embeddings, {meta_count} meta-entities")


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

    # rebuild: clear caches and rebuild embeddings/meta-entities
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
