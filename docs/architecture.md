# Architecture

How linked-past works, from server startup through query execution, cross-dataset discovery, and the viewer.

## System Overview

```
                    MCP Client (Claude Code, etc.)
                            │
                    MCP over streamable-http (:8000)
                            │
                ┌───────────┴───────────┐
                │      MCP Server       │
                │   (16 tools exposed)  │
                └───────────┬───────────┘
                            │
      ┌─────────────────────┼──────────────────────┐
      │                     │                      │
 Search Index         Linkage Graph          Dataset Registry
 (SQLite FTS5)        (in-memory Oxigraph)   (plugin lifecycle)
      │                     │                      │
      │              Curated YAML +          7 Dataset Plugins
      │              Wikidata TTL            (DatasetPlugin base)
      │                                           │
 examples, tips,                            ┌─────┴─────┐
 schema labels,                             │  context/  │
 entity labels                              │  (YAML)    │
                                            └─────┬─────┘
                                                  │
                                           Oxigraph Stores
                                           (read-only, per-dataset)
                                                  │
                                           OCI Artifacts
                                           (ghcr.io, via ORAS)
```

## Packages

The project is a uv workspace monorepo with three packages:

| Package | Description | License |
|---------|-------------|---------|
| **linked-past** | MCP server, dataset plugins, validation, linkage, search | AGPL-3.0 |
| **linked-past-store** | OCI distribution library (push, pull, sanitize, verify, cache) | LGPL-3.0 |
| **linked-past-viewer** | React web UI for browsing session results | AGPL-3.0 |

## MCP Server

### Entry Point

`linked-past-server` (defined in `linked_past.core.server:main`). Subcommands: `serve`, `init`, `status`, `update`, `reload`, `reindex`.

### Startup Sequence

```
main()
  │
  ├─ discover_plugins()              # Find all DatasetPlugin subclasses
  │    └─ imports linked_past.datasets   (triggers __subclasses__() registration)
  │
  ├─ DatasetRegistry(data_dir)
  │    └─ register(plugin) × 7       # DPRR, Pleiades, PeriodO, Nomisma, CRRO, OCRE, EDH
  │
  ├─ registry.initialize_cached()    # Open existing stores read-only (no downloads)
  │    └─ For each dataset with store/ on disk:
  │         ├─ get_read_only_store()
  │         ├─ _load_void()          # VoID class counts for validation hints
  │         └─ _load_schema()        # Merge auto-detected classes into plugin
  │
  ├─ LinkageGraph()                  # In-memory Oxigraph store
  │    ├─ load_yaml() × N            # Curated YAML links with PROV-O provenance
  │    └─ load_turtle() × N          # Wikidata concordances
  │
  ├─ _build_search_index()           # SQLite FTS5
  │    ├─ Check fingerprint           (skip if cached index still valid)
  │    └─ _index_dataset() × 7       # Schema, examples, tips, entity labels, SKOS vocabs
  │
  ├─ MetaEntityIndex()               # Cross-dataset entity clusters
  │    └─ Build from linkage graph + dataset stores
  │
  └─ FastMCP server ready on :8000
```

### Plugin System

Each dataset plugin is a Python class inheriting from `DatasetPlugin`:

```
DatasetPlugin (base class)
  │
  ├─ Class attributes: name, display_name, description, citation, license, url, ...
  │
  ├─ __init__()         # Auto-loads YAML from _context_dir()
  │    ├─ load_prefixes()
  │    ├─ load_schemas()
  │    ├─ load_examples()
  │    ├─ load_tips()
  │    └─ build_schema_dict()
  │
  ├─ fetch()            # Pull OCI artifact (default: ORAS)
  ├─ load()             # Bulk-load TTL + ontology sidecar + SKOS + materialize
  ├─ get_prefixes()     # Namespace map
  ├─ get_schema()       # Rendered markdown documentation
  ├─ build_schema_dict()# Structured schema for validation
  ├─ validate()         # Semantic checks against schema dict
  ├─ get_relevant_context()  # Tips/examples matching a SPARQL query
  └─ get_version_info() # Version metadata for registry.json
```

Most plugins are metadata-only (~20 lines). DPRR, CRRO, and OCRE override `get_version_info()` for custom source URLs. The `_context_dir()` classmethod auto-resolves to `{plugin_module}/context/`.

### YAML Context Files

The ontology source of truth for each dataset:

| File | Purpose |
|------|---------|
| `prefixes.yaml` | Namespace prefix map (e.g., `vocab: "http://romanrepublic.ac.uk/rdf/ontology#"`) |
| `schemas.yaml` | Classes with properties, ranges, and descriptions |
| `examples.yaml` | Natural language questions paired with SPARQL queries |
| `tips.yaml` | Query patterns and pitfalls, scoped to classes or cross-cutting |

### Tool Handlers

```
┌──────────────────┬──────────────────────────────────────────────────────┐
│ Tool             │ Purpose                                              │
├──────────────────┼──────────────────────────────────────────────────────┤
│ discover_datasets│ List datasets, filter by topic                       │
│ get_schema       │ Ontology documentation for a dataset                 │
│ validate_sparql  │ Check SPARQL syntax + semantics before execution     │
│ query            │ Execute SPARQL SELECT against a dataset store        │
│ search_entities  │ Full-text search across entity labels                │
│ explore_entity   │ Get properties, types, cross-refs for a URI          │
│ find_links       │ Cross-dataset references for a URI                   │
│ get_provenance   │ Scholarly citations for linked data                  │
│ update_dataset   │ Pull/reload datasets, check status                   │
│ disambiguate     │ Match a person against DPRR candidates               │
│ analyze_question │ Extract entities/datasets from a natural language Q   │
│ export_report    │ Export session as markdown/JSON/provenance table      │
│ start_viewer     │ Activate the web viewer                              │
│ stop_viewer      │ Deactivate the web viewer                            │
│ push_to_viewer   │ Send content to the viewer feed                      │
└──────────────────┴──────────────────────────────────────────────────────┘
```

### Validation Pipeline

Three-tier SPARQL validation before query execution:

1. **Syntax** — Parse via rdflib; report syntax errors
2. **Prefix auto-repair** — Scan for undefined prefixes; auto-insert `PREFIX` declarations
3. **Semantic checks** — Validate classes and predicates against the schema dict. Unknown terms are **warnings** (not errors)

Empty-result diagnostics (`diagnose_empty_result`) run additional probes:
- ASK on base pattern (stripped filters) to distinguish "no data" from "filters too restrictive"
- Individual filter isolation to identify the culprit
- Triple pattern decomposition to find broken joins

### Audit Logging

Every tool call is logged via `_log_tool_call()`:
- Appended to in-memory session log (for provenance export)
- Emits structured `logger.info` with `tool=`, `dataset=`, `duration=`, `output_len=`
- Error paths log at `WARNING` (timeout) or `ERROR` (store error, exception)

Log format matches uvicorn's colorized output: `INFO:     linked_past.core.server: tool=query dataset=dprr duration=42ms`

## Viewer

### Architecture

```
Browser                           MCP Server (:8000)
  │                                     │
  ├─ GET /viewer                        │
  │    └─ Serves React SPA              │
  │       (Vite build in dist/)         │
  │                                     │
  ├─ WebSocket /viewer/ws               │
  │    └─ Live feed of tool results ◄───┤ ViewerManager broadcasts
  │                                     │ JSON messages per tool call
  │                                     │
  ├─ GET /viewer/api/entity?uri=...     │
  │    └─ Entity properties + xrefs ◄───┤ Queries dataset store + linkage
  │                                     │
  ├─ GET /viewer/api/sessions           │
  │    └─ List past session files   ◄───┤ Reads JSONL from data dir
  │                                     │
  └─ GET /viewer/api/sessions/:id       │
       └─ Load past session messages◄───┤ Parses JSONL file
```

### Components

```
ViewerLayout
  ├─ Header
  │    ├─ SessionPicker         # Dropdown to switch sessions, ?session= URL param
  │    ├─ FeedFilters           # Toggle chips for tool types + datasets
  │    ├─ ExpandCollapseButtons # Lucide: ChevronsUpDown / ChevronsDownUp
  │    ├─ AutoScrollButton      # Lucide: ArrowDownToLine
  │    ├─ ExportButton          # Markdown export, Lucide: Download
  │    ├─ DarkModeToggle        # Lucide: Sun / Moon
  │    └─ ConnectionStatus      # Lucide: Wifi / WifiOff
  │
  └─ Feed
       └─ FeedItem × N          # Collapsible message cards
            ├─ Type badge        # QUERY/SEARCH/ENTITY/LINKS/REPORT with Lucide icons
            ├─ DatasetBadge      # Color-coded, hover shows dataset info
            ├─ Bookmark / Copy   # Lucide: Bookmark, Copy
            │
            └─ Message body (varies by type):
                 ├─ QueryResult       # Table with EntityUri pills, expandable cells
                 ├─ SearchResults     # Grouped by dataset, entity pills
                 ├─ EntityCard        # Properties, xrefs, see-also links
                 ├─ XrefList          # Cross-references with confidence
                 └─ MarkdownReport    # Rendered markdown with entity links
```

### Entity URI Rendering

Entity URIs are rendered as **dataset-colored pills** throughout the UI:

```
┌──────────────────┐  ┌───────────┐
│ crro:rrc-494.13  │  │ nm:aureus │
└──────────────────┘  └───────────┘
  (warm orange bg)      (golden bg)
```

- Colors use oklch color ramps with explicit light/dark mode values (CSS custom properties)
- Hover shows entity popover (properties, type hierarchy, cross-refs)
- Click navigates to the external URI (http→https, `%23`→`#` normalization, `#this` stripping)
- `shortUri()` compresses full URIs to prefixed form (e.g., `http://nomisma.org/id/rome` → `nm:rome`)

### Markdown Export

The Export button serializes all visible messages to markdown:
- Query titles included in headers
- Entity URIs rendered as markdown links: `[nm:rome](https://nomisma.org/id/rome)`
- Sequence numbers and timestamps on each message
- SPARQL blocks in fenced code blocks

## Store Management

### Data Directory

Follows XDG conventions:

1. `LINKED_PAST_DATA_DIR` (env var, or `/data` in Docker)
2. `$XDG_DATA_HOME/linked-past/`
3. `~/.local/share/linked-past/`

### Read-Only Stores

After initialization, all Oxigraph stores are opened **read-only** to avoid file locking. To update a dataset, the store is deleted and rebuilt from the OCI artifact.

### RDFS Materialization

`DatasetPlugin.load()` runs `materialize()` after bulk-loading raw triples:

1. Load `_ontology.ttl` sidecar (dataset-specific, e.g., Nomisma for CRRO/OCRE)
2. Load bundled SKOS ontology (infers `rdfs:label` from `skos:prefLabel` for all datasets)
3. `reasonable` (Rust OWL2 RL reasoner) computes deductive closure
4. New triples inserted; duplicates skipped
5. Fast no-op for datasets without RDFS/OWL axioms

## Cross-Dataset Linkage

### Curated Links

YAML files in `linkages/` with PROV-O provenance:
- `dprr_nomisma_confirmed.yaml` — Person links (moneyers, magistrates)
- `dprr_pleiades.yaml` — Province → place links
- `dprr_periodo.yaml` — Temporal period links
- `dprr_edh_confirmed.yaml` — DPRR persons in EDH inscriptions

### Wikidata Concordances

Turtle files in `linkages/wikidata/`:
- `nomisma_pleiades.ttl` — Mints → places
- `pleiades_tm_places.ttl` — Pleiades → Trismegistos

### Runtime Discovery

`find_links` and `explore_entity` also query dataset stores for SKOS/OWL predicates (`skos:closeMatch`, `skos:exactMatch`, `owl:sameAs`) at query time.

## OCI Distribution

See [Data Lifecycle](data-lifecycle.md) for the full pipeline.

Datasets are OCI artifacts at `ghcr.io/gillisandrew/linked-past/datasets/{name}:latest` with layer-level caching via the linked-past-store package.
