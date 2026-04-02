# Data Lifecycle

How datasets flow from upstream sources through the pipeline to the user's local store.

## Overview

```
 Upstream Source          OCI Registry (ghcr.io)              Local Store
 ─────────────          ──────────────────────              ───────────

  DPRR website     ┌─────────┐    ┌──────────┐    ┌──────────────────┐
  Nomisma RDF  ──→ │  ingest │──→ │ raw/     │    │  /data/{name}/   │
  Pleiades dump    │  script │    │ {name}:  │    │                  │
  EDH SPARQL       └─────────┘    │ latest   │    │  *.ttl           │
  ...                             └────┬─────┘    │  _void.ttl       │
                                       │          │  _schema.yaml    │
                                       ▼          │  _ontology.ttl   │
                                  ┌──────────┐    │  store/           │
                                  │  clean   │    │    (Oxigraph)    │
                                  │  dataset │    └────────┬─────────┘
                                  └────┬─────┘             │
                                       │            ┌──────┴───────┐
                                       ▼            │              │
                                  ┌──────────┐      │  materialize │
                                  │ datasets/│  ──→ │  (reasonable)│
                                  │ {name}:  │      │              │
                                  │ latest   │      │  + SKOS      │
                                  └──────────┘      │  + _ontology │
                                                    └──────────────┘
```

## Pipeline Stages

### 1. Ingest (raw)

Each dataset has an ingest script (`scripts/ingest_*.py` or `scripts/ingest_generic.py`) that:

1. Downloads from the upstream source (HTTP, SPARQL endpoint, tar.gz, etc.)
2. Converts to Turtle if needed (RDF/XML → Turtle via `rapper`, JSON-LD → Turtle via `rdflib`)
3. Pushes the raw Turtle to the OCI registry as `ghcr.io/gillisandrew/linked-past/raw/{name}:latest`

Configuration for each dataset lives in `datasets.yaml`:

```yaml
dprr:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/dprr:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/dprr:latest
  ingest_script: scripts/ingest_dprr.py
  min_triple_count: 600000
  license: CC-BY-NC-4.0
  source_url: https://romanrepublic.ac.uk
```

### 2. Clean (sanitize + metadata)

`scripts/clean_dataset.py` pulls the raw artifact and produces a clean version:

1. **Sanitize** — Fix encoding issues (truncated language subtags, bare DOIs, RDF/XML conversion artifacts)
2. **Verify** — Confirm the Turtle parses correctly and meets the minimum triple count threshold
3. **Generate VoID** — Produce `_void.ttl` with dataset statistics (triple count, class partitions, property counts)
4. **Extract schema** — Produce `_schema.yaml` with auto-detected classes and their properties
5. **Fetch ontology** — For datasets that depend on an external ontology (CRRO/OCRE use Nomisma), download it as `_ontology.ttl`
6. **Schema diff** — Compare against the previous version and report added/removed/changed classes
7. **Push** — Push the clean artifact with all sidecars to `ghcr.io/gillisandrew/linked-past/datasets/{name}:latest`

The clean artifact contains:

| File | Purpose |
|------|---------|
| `{name}.ttl` | The RDF data |
| `_void.ttl` | VoID metadata (triple count, class partitions) |
| `_schema.yaml` | Auto-extracted ontology (classes, properties, ranges) |
| `_ontology.ttl` | External ontology (optional, e.g., Nomisma for CRRO/OCRE) |

### 3. Load (local store initialization)

When a user runs `linked-past-server init` or `update_dataset`, the registry:

1. **Pull** — Downloads the clean OCI artifact via ORAS (with layer-level caching)
2. **Bulk-load** — Loads all `*.ttl` files (skipping `_*` sidecars) into a new Oxigraph store
3. **Load ontology sidecar** — If `_ontology.ttl` exists, loads it into the store (provides RDFS/OWL axioms for materialization)
4. **Load bundled ontologies** — Loads standard ontologies shipped with the package (currently SKOS) for universal inference
5. **Materialize** — Runs `reasonable` (Rust OWL2 RL reasoner) to infer triples from `rdfs:subPropertyOf`, `rdfs:subClassOf`, and other axioms
6. **Open read-only** — Closes the writable store and reopens it read-only (avoids file locking)
7. **Load VoID** — Parses `_void.ttl` for class counts (used as validation hints)
8. **Merge auto-schema** — Merges `_schema.yaml` classes into the plugin's hand-written schemas
9. **Save metadata** — Writes version info to `registry.json`

### 4. Indexing

After all datasets are loaded, the server builds two caches:

**Search index** (`search.db`) — SQLite FTS5 full-text index containing:
- Dataset metadata (name, description)
- SPARQL examples and tips from each plugin's YAML context
- Schema labels and comments
- Entity labels (`rdfs:label`, `skos:prefLabel`, `dcterms:title`) from all stores
- SKOS vocabulary terms with definitions
- Enriched coin type labels (CRRO/OCRE with issuer names from Nomisma)

**Meta-entity index** (`meta_entities.db`) — Unified cross-dataset entity clusters built from the linkage graph and Wikidata concordances.

Both are cached on disk with a fingerprint. If the fingerprint matches on next startup, the cache is reused.

## RDFS/OWL Materialization

Oxigraph has no built-in inference engine. The `materialize()` function bridges this gap:

```
Raw triples (427K for DPRR)
    │
    ▼
Serialize to temp Turtle file
    │
    ▼
reasonable.PyReasoner (Rust OWL2 RL)
    │
    ▼
Inferred triples (e.g., +322K for DPRR)
    │
    ▼
Deduplicate and insert new triples
    │
    ▼
Final store (749K for DPRR)
```

Key inferences:
- **`rdfs:subPropertyOf`** — `hasPersonName` → `rdfs:label` (DPRR), `skos:prefLabel` → `rdfs:label` (all SKOS datasets), `hasStartDate` → `hasDate` (Nomisma)
- **`rdfs:subClassOf`** — `Person` → `ThingWithName` (DPRR), `Hoard` → `Find` → `Context` (Nomisma)

Fast no-op for datasets without RDFS/OWL axioms (Pleiades, PeriodO, EDH).

## CLI Commands

| Command | What it does |
|---------|-------------|
| `init [datasets...] --all` | First-time download + load |
| `update [datasets...] --force` | Re-pull from OCI + reload store + rebuild search |
| `reload [datasets...]` | Re-load stores from existing TTL files on disk (no download) |
| `reindex` | Rebuild search + meta-entity caches from existing stores |
| `status` | Show installed datasets with triple counts |

## Data Directory Layout

```
/data/                          (LINKED_PAST_DATA_DIR)
├── registry.json               # Version, triple count, license per dataset
├── search.db                   # FTS5 search index
├── search.fingerprint          # Cache validity check
├── meta_entities.db            # Unified entity index
├── dprr/
│   ├── store/                  # Oxigraph persistent store (opened read-only)
│   ├── dprr.ttl                # Raw RDF data
│   ├── _void.ttl               # VoID metadata
│   ├── _schema.yaml            # Auto-extracted schema
│   └── _ontology.ttl           # Bundled ontology (if applicable)
├── nomisma/
│   ├── store/
│   ├── nomisma.ttl
│   ├── _void.ttl
│   ├── _schema.yaml
│   └── _ontology.ttl
├── crro/
│   ├── store/
│   ├── crro.ttl
│   ├── _void.ttl
│   └── _schema.yaml            # No _ontology.ttl — uses Nomisma's via OCI
└── ...
```

## OCI Artifact Structure

Each clean dataset is an OCI artifact with multiple layers:

```
ghcr.io/gillisandrew/linked-past/datasets/dprr:latest
  ├── Layer 1: dprr.ttl           (26 MB, application/vnd.oci.image.layer.v1.tar)
  ├── Layer 2: _void.ttl          (2 KB)
  ├── Layer 3: _schema.yaml       (8 KB)
  └── Manifest annotations:
        org.opencontainers.image.licenses: CC-BY-NC-4.0
        org.opencontainers.image.source: https://romanrepublic.ac.uk
        io.github.gillisandrew.linked-past.citation: "Mouritsen et al. (2017)..."
        io.github.gillisandrew.linked-past.triples: "427281"
```

The linked-past-store package provides layer-level caching: if only `_void.ttl` changes between versions, only that layer is re-downloaded.
