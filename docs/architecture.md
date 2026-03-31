# Architecture

A consolidated guide to how linked-past works, from server startup through query execution and cross-dataset discovery.

## System Overview

```
                        MCP Client (Claude Code, etc.)
                                │
                        MCP over streamable-http (:8000)
                                │
                    ┌───────────┴───────────┐
                    │     MCP Server         │
                    │  (10 tools exposed)    │
                    └───────────┬───────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
    Embedding Index      Linkage Graph         Dataset Registry
    (fastembed+SQLite)   (in-memory Oxigraph)  (plugin lifecycle)
          │                     │                     │
          │              Curated YAML +         7 Dataset Plugins
          │              Wikidata TTL           (DatasetPlugin ABC)
          │                                          │
    examples, tips,                            ┌─────┴─────┐
    schema labels                              │  context/  │
                                               │  (YAML)    │
                                               └─────┬─────┘
                                                     │
                                              Oxigraph Stores
                                              (read-only, per-dataset)
                                                     │
                                              OCI Artifacts
                                              (ghcr.io, via ORAS)
```

## Packages

The project is a uv workspace monorepo with two packages:

- **linked-past** — MCP server, dataset plugins, validation, linkage, embeddings. Licensed AGPL-3.0.
- **linked-past-store** — Standalone OCI distribution library (push, pull, sanitize, verify, cache). Licensed LGPL-3.0. Used by linked-past for fetching datasets, but also usable independently.

## Server Startup

Entry point: `linked-past-server` (defined in `linked_past.core.server:main`).

### Startup Sequence

1. **Register plugins** — All 7 dataset plugins are instantiated and registered with `DatasetRegistry`. Each plugin loads its YAML context (prefixes, schemas, examples, tips) on `__init__`.

2. **Initialize cached stores** — `registry.initialize_cached()` scans the data directory. For each dataset with an existing `store/` directory, it opens the Oxigraph store **read-only**. Datasets without local stores are skipped (no network calls).

3. **Build linkage graph** — An in-memory Oxigraph store is populated from:
   - Curated YAML files in `linkages/` (e.g., `dprr_nomisma_confirmed.yaml`)
   - Wikidata-derived Turtle files in `linkages/wikidata/`
   - Each link gets PROV-O provenance triples (confidence, basis, method, author)

4. **Build embedding index** — fastembed (BAAI/bge-small-en-v1.5) indexes searchable content from all initialized datasets:
   - Dataset metadata (name, description)
   - SPARQL examples (question + query)
   - Query tips (title + body)
   - Schema labels and comments
   - Meta-entity descriptions

   First startup downloads the model (~50 MB). Subsequent startups load from the SQLite cache.

5. **Build meta-entities** — Clusters linked entities from the linkage graph into unified `MetaEntity` objects. Cached in SQLite (`meta_entities.db`).

6. **Server ready** — FastMCP server listens on port 8000 for streamable-http connections.

### Lazy Dataset Loading

Datasets not present on disk are **not downloaded at startup**. To initialize a new dataset, a client calls `update_dataset(dataset="name")`, which triggers:

1. `plugin.fetch()` → pulls OCI artifact via linked-past-store
2. `plugin.load()` → bulk-loads RDF into a new Oxigraph store
3. Store opens read-only; metadata saved to `registry.json`
4. Embeddings and meta-entities are rebuilt to include the new dataset

## Data Flow

### Query Execution

```
Client: query(sparql, dataset)
  │
  ├─ 1. Validate SPARQL (syntax + prefix auto-repair + semantic checks)
  │
  ├─ 2. Execute against dataset's Oxigraph store
  │     └─ Timeout: LINKED_PAST_QUERY_TIMEOUT (default 600s)
  │
  ├─ 3. Format results as markdown table (via toons)
  │
  ├─ 4. Append cross-dataset "See also" suggestions
  │     ├─ Scan result URIs for SKOS/OWL predicates in all stores
  │     └─ Check linkage graph for curated links
  │
  └─ 5. Append citation footer (dataset name, version, license)
```

### Entity Discovery

```
Client: search_entities(query_text, dataset?)
  │
  ├─ 1. Check meta-entities (unified cross-dataset view)
  │     └─ Substring match on canonical name
  │
  ├─ 2. Search per-dataset stores via SPARQL
  │     └─ FILTER(CONTAINS(LCASE(?label), LCASE(query)))
  │
  └─ 3. Return combined results with dataset attribution
```

### Cross-Dataset Linking

```
Client: find_links(uri)
  │
  ├─ 1. Query linkage graph (curated YAML + Wikidata concordances)
  │     └─ Returns: target URI, relationship, confidence, basis
  │
  ├─ 2. Query all dataset stores for SKOS/OWL predicates
  │     └─ skos:closeMatch, skos:exactMatch, owl:sameAs
  │
  └─ 3. Merge and deduplicate results
```

## Plugin System

Each dataset lives in `linked_past/datasets/{name}/` with:

```
{name}/
├── __init__.py
├── plugin.py       # DatasetPlugin ABC implementation
└── context/
    ├── prefixes.yaml   # Namespace prefix map
    ├── schemas.yaml    # Class definitions with properties
    ├── examples.yaml   # SPARQL example queries
    └── tips.yaml       # Query tips and patterns
```

### DatasetPlugin ABC

Plugins declare metadata as class attributes (`name`, `display_name`, `description`, `citation`, `license`, `url`, `time_coverage`, `spatial_coverage`, `oci_dataset`, `oci_version`) and implement:

- `get_prefixes()` — namespace map for SPARQL queries
- `get_schema()` — rendered markdown documentation
- `build_schema_dict()` — structured schema for validation
- `validate(sparql)` — dataset-specific semantic checks
- `get_version_info(data_dir)` — version metadata

Default implementations handle `fetch()` (OCI pull via linked-past-store) and `load()` (bulk-load all `.ttl` files into Oxigraph).

### YAML Context Files

YAML files are the **ontology source of truth**. To change a dataset's schema, edit the YAML files, not Python code.

- **prefixes.yaml** — Short names → URIs (e.g., `vocab: "http://romanrepublic.ac.uk/rdf/ontology#"`)
- **schemas.yaml** — Classes with properties, ranges, and descriptions. Hand-written schemas are merged with auto-generated schemas extracted from the OCI artifact's `_schema.yaml` sidecar.
- **examples.yaml** — Natural language questions paired with SPARQL queries. Used for embedding search and as few-shot examples.
- **tips.yaml** — Query patterns and pitfalls. Can be scoped to specific classes or cross-cutting.

## Validation Pipeline

Three-tier SPARQL validation before query execution:

1. **Syntax** — Parse SPARQL; report syntax errors.
2. **Prefix auto-repair** — Scan for undefined prefixes; auto-insert `PREFIX` declarations from the plugin's prefix map.
3. **Semantic checks** — Validate classes and predicates against the dataset's schema dict. Unknown terms are **warnings** (not errors) because multi-vocabulary datasets use shared ontologies (LAWD, FOAF, SKOS, Dublin Core, ORG) whose terms aren't in the dataset-specific YAML.

## Store Management

### Data Directory

Follows XDG conventions:

1. `LINKED_PAST_DATA_DIR` environment variable (if set)
2. `$XDG_DATA_HOME/linked-past/` (if XDG_DATA_HOME set)
3. `~/.local/share/linked-past/` (default)

Layout:

```
{data_dir}/
├── registry.json           # Version, triple count, license per dataset
├── meta_entities.db        # Unified entity index (SQLite)
├── embeddings.db           # Embedding vectors (SQLite)
├── dprr/
│   ├── store/              # Oxigraph persistent store
│   ├── dprr.ttl            # Raw RDF data
│   ├── _void.ttl           # VoID metadata (sidecar)
│   └── _schema.yaml        # Auto-extracted ontology (sidecar)
├── pleiades/
│   ├── store/
│   └── ...
└── ...
```

### Read-Only Stores

After initialization, all Oxigraph stores are opened **read-only** to avoid file locking issues. No write operations should be performed on initialized stores. To update a dataset, the store is deleted and rebuilt from the OCI artifact.

## Cross-Dataset Linkage

### Curated Links

YAML files in `linkages/` define manually verified cross-references:

- `dprr_nomisma_confirmed.yaml` — 193 person links (moneyers, magistrates)
- `dprr_nomisma_probable.yaml` — candidates awaiting review
- `dprr_edh_confirmed.yaml` — DPRR persons matched to EDH inscriptions
- `dprr_periodo.yaml` — temporal period links
- `dprr_pleiades.yaml` — geographic province links

Each link carries PROV-O provenance: confidence level (confirmed/probable/candidate), basis, method, author, and date.

### Wikidata Concordances

Turtle files in `linkages/wikidata/` contain cross-references extracted from Wikidata:

- `nomisma_pleiades.ttl` — Nomisma mints to Pleiades places
- `pleiades_tm_places.ttl` — Pleiades to Trismegistos places

### Runtime Discovery

`find_links` and `explore_entity` also query all dataset stores for SKOS/OWL predicates (`skos:closeMatch`, `skos:exactMatch`, `owl:sameAs`) at query time, discovering links embedded in the datasets themselves.

## OCI Distribution

Datasets are distributed as OCI artifacts via container registries:

```
ghcr.io/gillisandrew/linked-past/datasets/{dataset}:{version}
```

Each artifact contains:
- **Primary layer**: `{dataset}.ttl` (the RDF data)
- **Sidecar layers**: `_void.ttl` (VoID metadata), `_schema.yaml` (extracted ontology)
- **Manifest annotations**: license (SPDX), source URL, citation, triple count, format

The linked-past-store package handles push, pull, sanitization, and verification. See [its README](../packages/linked-past-store/README.md) for details on the caching system.
