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

## Data Cleaning

Upstream scholarly datasets are not produced with strict RDF parsers in mind. The pipeline has encountered — and now automatically fixes — the following classes of issues.

### Catalog of upstream data issues

#### XML-level issues (pre-parser)

These break the XML parser before RDF semantics are even considered.

| Issue | Example | Datasets | Fix |
| ----- | ------- | -------- | --- |
| Undefined HTML entities | `R.&nbsp;Martini` in text content | RPC | DOCTYPE injection: `<!ENTITY nbsp "&#160;">` |
| Server blocks bot User-Agents | HTTP 403 for default `Python-urllib` UA | RPC | Send `User-Agent: linked-past/1.0` header |

#### IRI-level issues (valid XML, invalid RDF)

The XML parses, but the IRI values violate RFC 3987.

| Issue | Example | Datasets | Fix |
| ----- | ------- | -------- | --- |
| Placeholder IRIs | `rdf:resource="-"`, `rdf:resource="—"` | RPC | Drop the attribute (meaningless) |
| Trailing whitespace in IRIs | `rdf:resource="http://lgpn.ox.ac.uk/id/V5a-54230 "` | RPC | Strip whitespace |
| Interior spaces in IRIs | spaces inside URI local names | RPC | Percent-encode to `%20` |
| Unicode replacement chars in IRIs | `Ayd�nc�k` in DBpedia URI (Turkish ı/ğ lost upstream) | Nomisma | Correct to known-good percent-encoded URI (`Ayd%C4%B1nc%C4%B1k`) |
| Bare DOIs missing scheme | `<doi.org/10.1234/test>` | Pleiades | Prepend `https://` |

#### Turtle-level issues (valid RDF/XML, breaks strict Turtle parsers)

These only appear after RDF/XML → Turtle conversion or in native Turtle sources.

| Issue | Example | Datasets | Fix |
| ----- | ------- | -------- | --- |
| BCP 47 language subtags > 8 chars | `"Vatl"@etruscan-in-latin-characters` (10 occurrences) | Pleiades | Replace with RFC 5646 private-use tag `@x-etruscan-latn`; unknown tags: drop oversized subtags at boundaries |
| URI fragment encoding (`%23` vs `#`) | `pleiades:433134%23this` instead of `#this` (~100K IRIs) | Pleiades | `%23` → `#` replacement at ingest (blanket — all are fragments) |
| Missing path segment in vocabulary URIs | `/vocabularies/abbey` instead of `/vocabularies/place-types/abbey` (~159K IRIs) | Pleiades | Insert `place-types/` segment at ingest |

#### Semantic-level issues (valid RDF, wrong triples)

Technically parseable but produce incorrect or duplicate data.

| Issue | Example | Datasets | Fix |
| ----- | ------- | -------- | --- |
| Language tags lost during materialization | `"Julius Caesar"@en` → untagged `"Julius Caesar"` duplicate | All (during RDFS inference) | Preserve `rdflib.Literal.language` and `.datatype` when converting reasoner output to pyoxigraph terms |
| Incorrect ontology namespace | `lawd:` at `http://lawd.info/ontology/1.0/` vs correct `http://lawd.info/ontology/` | EDH | Fix prefix in schema YAML |

### Current cleaning architecture

Cleaning happens at two pipeline stages:

**Ingest stage** (per-dataset scripts): handles source-format-specific issues before the data reaches OCI. Each dataset's ingest script owns its own quirks:

- `ingest_generic.py` — RDF/XML sources (CRRO, OCRE, RPC): DOCTYPE entity injection + SAX IRI rewrite + pyoxigraph conversion
- `ingest_nomisma.py` — strips lines with Unicode replacement characters after conversion
- `ingest_pleiades.py` — concatenates multi-file tar.gz (BCP 47 / DOI fixes deferred to clean stage)

**Clean stage** (`clean_dataset.py`): dataset-agnostic sanitization via `linked_past_store.sanitize_turtle()`:

1. Regex pre-fixes on input (bare DOIs, BCP 47 language tags)
2. Format normalization (currently via rapper, being replaced by pyoxigraph)
3. Regex post-fixes on output (catches anything the converter preserved verbatim)
4. Strict verification via pyoxigraph `bulk_load`

### Replacing rapper with pyoxigraph

The pipeline originally used `rapper` (Raptor RDF parser, a C system binary) for lenient RDF/XML → Turtle conversion. This had drawbacks:

- **External dependency**: `rapper` must be installed on the host and in CI
- **Silent leniency**: rapper accepts many malformed inputs without error, so bad data can slip through undetected
- **No IRI repair**: rapper doesn't fix placeholder IRIs, trailing whitespace, or other IRI-level issues — those needed separate patches

The replacement approach uses a two-phase pipeline built entirely on stdlib + pyoxigraph (already a project dependency):

**Phase 1: SAX streaming rewrite** (stdlib `xml.sax`)

A namespace-aware SAX handler streams through the RDF/XML in a single pass with constant memory:

1. Injects DOCTYPE with common HTML entities (`&nbsp;`, `&mdash;`, `&ndash;`)
2. Sanitizes `rdf:resource`, `rdf:about`, `rdf:datatype` attributes (strip, encode, drop placeholders)
3. Passes all other content through unchanged

**Phase 2: pyoxigraph strict parse**

The cleaned RDF/XML is loaded via `bulk_load(format=RdfFormat.RDF_XML)` and serialized to Turtle. pyoxigraph is strict — if phase 1 missed an issue, it fails loudly rather than producing silently broken data.

On the RPC dataset (149 MB RDF/XML, 1.65M triples), the full SAX + pyoxigraph pipeline completes in ~16 seconds with no external dependencies.

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
