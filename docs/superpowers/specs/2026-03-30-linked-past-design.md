# Linked Past: Multi-Dataset Prosopographical MCP Server

**Date:** 2026-03-30
**Status:** Draft
**Author:** gillisandrew + Claude

## Vision

Make linked ancient world datasets accessible to AI agents so scholars can give natural language queries and receive well-cited results with easy ways to further explore across datasets.

## Scope

### In Scope (v1)

- Plugin architecture within the existing `dprr-tool` repo
- Core server with dataset-agnostic store management, validation, and tool routing
- Five dataset plugins: DPRR, POMS, Pleiades, PeriodO, Nomisma
- Linkage graph with provenance for cross-dataset references
- Embedding-assisted retrieval for query routing and example selection
- Eight discovery-oriented MCP tools
- Pinned snapshots with manual update mechanism
- Layered citation model (concise by default, full provenance on demand)

### Out of Scope (v1)

- Datasets without RDF access (PBE, CCEd, PASE, PBW, Charlemagne's Europe) — architecture supports adding them later
- User/agent-contributed linkages (data model supports it; no write tool in v1)
- Algorithmic link suggestion (candidate confidence level exists; no generation in v1)
- SPARQL federation against remote endpoints
- Scraping or converting web-only databases

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   MCP Tools Layer                    │
│  discover_datasets · get_schema · validate_sparql    │
│  query · explore_entity · get_provenance · find_links│
│  update_dataset                                      │
├─────────────────────────────────────────────────────┤
│              Embedding Retrieval Layer                │
│  fastembed (ONNX) → SQLite vector store              │
│  Indexes: examples, tips, schemas, dataset descs     │
├──────────────┬──────────────┬───────────────────────┤
│  Linkage     │   Core       │   Dataset Registry     │
│  Graph       │   Validation │   Plugin discovery     │
│  (Oxigraph)  │   Pipeline   │   & lifecycle          │
├──────────────┴──────────────┴───────────────────────┤
│                 Dataset Plugins                       │
│  ┌───────┐ ┌──────┐ ┌────────┐ ┌───────┐ ┌───────┐ │
│  │ DPRR  │ │ POMS │ │Pleiades│ │PeriodO│ │Nomisma│ │
│  │.ttl   │ │.rdf  │ │.ttl.gz │ │.jsonld│ │.ttl   │ │
│  └───┬───┘ └──┬───┘ └───┬────┘ └───┬───┘ └───┬───┘ │
│      │        │         │          │          │      │
├──────┴────────┴─────────┴──────────┴──────────┴─────┤
│              Oxigraph Stores (read-only)             │
│  {data_dir}/dprr/store/                              │
│  {data_dir}/poms/store/                              │
│  {data_dir}/pleiades/store/                          │
│  {data_dir}/periodo/store/                           │
│  {data_dir}/nomisma/store/                           │
│  {data_dir}/_linkages/store/                         │
│  {data_dir}/embeddings.db                            │
└─────────────────────────────────────────────────────┘
```

## Project Structure

```
linked_past/
├── core/
│   ├── server.py            # FastMCP server, tool registration, routing
│   ├── registry.py          # Dataset registry — discovers & loads plugins
│   ├── store.py             # Generic Oxigraph store management
│   ├── linkage.py           # Linkage graph store + provenance model
│   ├── validate.py          # Shared validation pipeline
│   ├── embeddings.py        # fastembed + SQLite vector retrieval
│   └── context.py           # YAML loading and rendering (generalized)
├── datasets/
│   ├── base.py              # DatasetPlugin abstract base class
│   ├── dprr/
│   │   ├── plugin.py        # DPRR-specific fetch, load, validation
│   │   └── context/
│   │       ├── schemas.yaml
│   │       ├── examples.yaml
│   │       ├── tips.yaml
│   │       └── prefixes.yaml
│   ├── poms/
│   │   ├── plugin.py
│   │   └── context/
│   │       ├── schemas.yaml
│   │       ├── examples.yaml
│   │       ├── tips.yaml
│   │       └── prefixes.yaml
│   ├── pleiades/
│   │   ├── plugin.py
│   │   └── context/ ...
│   ├── periodo/
│   │   ├── plugin.py        # JSON-LD → Turtle conversion
│   │   └── context/ ...
│   └── nomisma/
│       ├── plugin.py
│       └── context/ ...
├── linkages/
│   ├── dprr_pleiades.yaml   # ~92 province → place mappings
│   ├── dprr_periodo.yaml    # ~5-10 era → period definition mappings
│   ├── dprr_nomisma.yaml    # ~20-50 moneyer/person overlaps
│   └── poms_pleiades.yaml   # Scottish places → Pleiades
```

## Dataset Plugin Interface

```python
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass

@dataclass
class VersionInfo:
    version: str               # e.g., "v4.1", "1.3.0"
    source_url: str
    fetched_at: str            # ISO 8601
    triple_count: int
    rdf_format: str            # "turtle", "jsonld", etc.

@dataclass
class UpdateInfo:
    current: str
    available: str
    changelog_url: str | None

@dataclass
class ValidationResult:
    valid: bool
    sparql: str                # Possibly prefix-repaired
    errors: list[str]
    suggestions: list[str]

class DatasetPlugin(ABC):
    name: str                  # e.g., "dprr"
    display_name: str          # e.g., "Digital Prosopography of the Roman Republic"
    description: str           # Scholarly description
    citation: str              # Canonical citation string
    license: str               # e.g., "CC BY-NC 4.0"
    url: str                   # Project homepage
    time_coverage: str         # e.g., "509-31 BC"
    spatial_coverage: str      # e.g., "Roman Republic"

    @abstractmethod
    def fetch(self, data_dir: Path) -> Path:
        """Download data, return path to RDF file(s)."""

    @abstractmethod
    def load(self, store, rdf_path: Path) -> int:
        """Bulk-load into Oxigraph store, return triple count."""

    @abstractmethod
    def get_prefixes(self) -> dict[str, str]:
        """Namespace prefix map."""

    @abstractmethod
    def get_schema(self) -> str:
        """Rendered ontology overview from YAML context."""

    @abstractmethod
    def validate(self, sparql: str, schema_dict: dict) -> ValidationResult:
        """Dataset-specific semantic validation."""

    @abstractmethod
    def get_version_info(self, data_dir: Path) -> VersionInfo:
        """Current snapshot metadata."""

    def check_for_updates(self) -> UpdateInfo | None:
        """Compare local vs upstream. Returns None if up to date."""
        return None
```

## MCP Tools

### 1. `discover_datasets`

```
discover_datasets(topic?: str) → str
```

- No args: table of all loaded datasets (name, period, geography, triple count, version, license, citation)
- With topic: embedding similarity search against dataset descriptions + class descriptions, returns ranked matches
- Always includes citation guidance for each dataset

### 2. `get_schema`

```
get_schema(dataset: str) → str
```

- Returns ontology overview for a specific dataset
- Format: PREFIX declarations, class summary (one-liner per class), cross-cutting tips
- Includes top-k relevant examples (retrieved via embeddings if the agent provides a topic hint)
- Same layered format as current DPRR `get_schema`

### 3. `validate_sparql`

```
validate_sparql(sparql: str, dataset: str) → str
```

- Tier 1: Parse + auto-repair missing PREFIXes (core, dataset-agnostic)
- Tier 2: Semantic validation against dataset's schema dict (dataset-specific)
- Returns: VALID/INVALID status, errors with suggestions, relevant tips + examples
- Includes unified diff showing prefix repairs

### 4. `query`

```
query(sparql: str, dataset: str, timeout?: int) → str
```

- Validates (tiers 1-2) then executes against the dataset's store
- Results in tabular format (toons)
- Footer includes dataset-level citation and version
- Timeout defaults to 600s, overridable per dataset via env vars

### 5. `explore_entity`

```
explore_entity(uri: str) → str
```

- Accepts any entity URI from any loaded dataset
- Determines home dataset from URI namespace
- Returns:
  - Entity properties from home dataset (key predicates, not a full dump)
  - Cross-links from linkage graph (with provenance summary)
  - Suggested next steps ("Query DPRR for office-holdings of this person", "See Pleiades for coordinates")
- The primary "follow the thread" exploration tool

### 6. `get_provenance`

```
get_provenance(uri: str, predicate?: str) → str
```

- Full provenance drill-down
- Without predicate: all provenance for the entity
- With predicate: provenance for a specific claim
- Returns: source → factoid → dataset chain, plus linkage basis for any cross-references
- Includes secondary source citations where available in the dataset (e.g., "Broughton, MRR I, p. 234")

### 7. `find_links`

```
find_links(uri: str) → str
```

- All cross-dataset links from the linkage graph
- Each link: target URI, relationship type, confidence level, who asserted it, scholarly basis
- Groups by confidence: confirmed, probable, candidate
- Also returns: "No confirmed links found. The following datasets may have relevant entities: ..." when the linkage graph has gaps

### 8. `update_dataset`

```
update_dataset(dataset?: str) → str
```

- No args: check all datasets for available updates
- With dataset: check specific dataset
- Reports: current version, available version, what changed
- On confirmation: fetch → close store → reload → reopen read-only → update registry → regenerate embeddings for that dataset
- Reports any linkage graph impacts (broken references)

## Linkage Graph

### Data Model

Each cross-reference is stored as a named graph with PROV-O provenance:

```turtle
# The link itself
GRAPH <linkage:{source-dataset}-{source-id}--{target-dataset}-{target-id}> {
    <source-uri>  <relationship>  <target-uri> .
}

# Provenance metadata
<linkage:{source-dataset}-{source-id}--{target-dataset}-{target-id}>
    prov:wasAttributedTo <linkage:agent/{who}> ;
    prov:generatedAtTime "2026-03-30"^^xsd:date ;
    dcterms:source "{scholarly basis}" ;
    linkpast:confidence linkpast:{confirmed|probable|candidate} ;
    linkpast:method linkpast:{manual_alignment|label_match|uri_match} .
```

### Relationship Types

| Relationship | Use Case |
|---|---|
| `owl:sameAs` | Same real-world entity across datasets |
| `skos:exactMatch` | Equivalent concepts |
| `skos:closeMatch` | Related but not identical |
| `dcterms:spatial` | Entity relates to a place |
| `dcterms:temporal` | Entity relates to a time period |

### Confidence Levels

| Level | Meaning |
|---|---|
| `confirmed` | Scholarly consensus or explicit cross-reference in source data |
| `probable` | Strong evidence requiring interpretation (name + date match) |
| `candidate` | Algorithmic suggestion, not yet reviewed |

### Shipped Linkages (v1)

| File | Content | Basis | Estimated count |
|---|---|---|---|
| `dprr_pleiades.yaml` | DPRR provinces → Pleiades places | Barrington Atlas | ~92 |
| `dprr_periodo.yaml` | DPRR date ranges → PeriodO period definitions | Standard periodizations | ~5-10 |
| `dprr_nomisma.yaml` | Late Republican persons → Nomisma authority records | Coin attribution | ~20-50 |
| `poms_pleiades.yaml` | Scottish medieval places → Pleiades entries | Where overlap exists | TBD — assess after inspecting POMS RDF |

### Linkage YAML Format

```yaml
# linkages/dprr_pleiades.yaml
metadata:
  source_dataset: dprr
  target_dataset: pleiades
  relationship: owl:sameAs
  confidence: confirmed
  method: manual_alignment
  basis: "Barrington Atlas of the Greek and Roman World (Talbert 2000)"
  author: "linked-past project"
  date: "2026-03-30"

links:
  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/Sicilia"
    target: "https://pleiades.stoa.org/places/462492#this"
    note: "Barrington Atlas, Map 47"

  - source: "http://romanrepublic.ac.uk/rdf/entity/Province/Africa"
    target: "https://pleiades.stoa.org/places/775#this"
    note: "Barrington Atlas, Map 33"
  # ...
```

## Embedding-Assisted Retrieval

### What Gets Embedded

| Document type | Source | Per dataset | Total estimate |
|---|---|---|---|
| Example queries | `examples.yaml` | ~20 | ~100 |
| Tips/pitfalls | `tips.yaml` | ~20 | ~100 |
| Class descriptions | `schemas.yaml` | ~15 | ~75 |
| Dataset descriptions | `plugin.py` | 1 | 5 |
| Linkage descriptions | `linkages/*.yaml` | 1 | ~5 |
| **Total** | | | **~300 documents** |

### Technical Implementation

- **Embedding model:** `fastembed` with ONNX runtime (no torch dependency). Default model: `BAAI/bge-small-en-v1.5` (~50MB, 384 dimensions).
- **Storage:** SQLite database at `{data_dir}/embeddings.db`
  - `documents` table: `id, dataset, doc_type, text, embedding BLOB`
  - `metadata` table: `model_name, generated_at, dataset_versions`
- **Search:** Brute-force cosine similarity in Python. At ~300 vectors of 384 dimensions, this takes microseconds.
- **Generation:** At dataset init time, after store load. Regenerates per-dataset when `update_dataset()` runs.
- **Staleness check:** On startup, compare dataset versions in `embeddings.db` metadata against `registry.json`. Regenerate if mismatched.

### Retrieval Flow

1. Scholar's natural language question arrives
2. Embed the question with fastembed
3. Retrieve top-k documents (k=10) across all types and datasets
4. Use results to:
   - Route `discover_datasets()` responses
   - Select relevant examples/tips for `get_schema()` and `validate_sparql()`
   - Suggest datasets in `explore_entity()` next steps

## Versioning & Citation

### Registry

```json
// {data_dir}/registry.json
{
  "dprr": {
    "version": "1.3.0",
    "source_url": "https://github.com/gillisandrew/dprr-tool/releases/...",
    "fetched_at": "2026-03-30T14:22:00Z",
    "triple_count": 2048576,
    "rdf_format": "turtle",
    "license": "CC BY-NC 4.0"
  },
  "pleiades": {
    "version": "v4.1",
    "source_url": "https://pleiades.stoa.org/downloads/pleiades-places-latest.ttl.gz",
    "fetched_at": "2026-03-30T15:01:00Z",
    "triple_count": 1250000,
    "rdf_format": "turtle",
    "license": "CC BY 3.0"
  }
}
```

### Citation in Results

**Default (query results footer):**
```
─── Sources ───
Data: Digital Prosopography of the Roman Republic (DPRR) v1.3.0,
      accessed 2026-03-30. CC BY-NC 4.0.
      Cite as: Sherwin et al., romanrepublic.ac.uk
Tool: linked-past v0.1.0, https://github.com/gillisandrew/dprr-tool
```

**Drill-down (get_provenance):**
```
─── Provenance ───
Claim: L. Iunius Brutus held office of consul in 509 BC
Source: Broughton, T.R.S., Magistrates of the Roman Republic, Vol. I, p. 1
Factoid: PostAssertion <http://romanrepublic.ac.uk/rdf/entity/PostAssertion/12345>
Dataset: DPRR v1.3.0 (romanrepublic.ac.uk, CC BY-NC 4.0)

Cross-reference: Province Sicilia = Pleiades 462492
Basis: Barrington Atlas, Map 47 (Talbert 2000)
Confidence: confirmed
Asserted by: linked-past project, 2026-03-30
```

## Migration Path

### What Moves Where

| Current | New Location | Changes |
|---|---|---|
| `dprr_mcp/mcp_server.py` | `linked_past/core/server.py` | Generalize tool registration |
| `dprr_mcp/store.py` | `linked_past/core/store.py` | Extract dataset-agnostic store ops |
| `dprr_mcp/validate.py` | `linked_past/core/validate.py` + `datasets/dprr/plugin.py` | Core keeps tier-1; tier-2 moves to plugin |
| `dprr_mcp/context/` | `linked_past/datasets/dprr/context/` | Unchanged YAML files |
| `dprr_mcp/context/__init__.py` | `linked_past/core/context.py` | Already dataset-agnostic |
| `dprr_mcp/fetch.py` | `linked_past/datasets/dprr/plugin.py` | Becomes plugin's `fetch()` |

### Package Rename

```toml
[project]
name = "linked-past"

[project.scripts]
linked-past-server = "linked_past.core.server:main"
dprr-server = "linked_past.core.server:main"  # backward compat
```

### Backward Compatibility

- `dprr-server` entry point continues to work
- `DPRR_DATA_DIR` and `DPRR_DATA_URL` env vars still work for DPRR dataset
- `LINKED_PAST_DATA_DIR` is the new general env var (takes precedence)
- Existing DPRR stores at `~/.local/share/dprr-mcp/` detected and migrated on first run

### New Dependencies

```toml
dependencies = [
    "pyoxigraph",          # existing
    "rdflib",              # existing
    "pyyaml",              # existing
    "mcp",                 # existing
    "toons>=0.5.3",        # existing
    "fastembed",           # NEW — ONNX-based embeddings
    "httpx",               # NEW — async HTTP for fetch (replaces urllib)
]
```

## Datasets: Source Details

### DPRR (migrated from current)
- **Source:** GitHub release tarball (dprr-data.tar.gz)
- **Format:** Turtle
- **Size:** ~34.5 MB, ~2M triples
- **License:** CC BY-NC 4.0
- **URI namespace:** `http://romanrepublic.ac.uk/rdf/`
- **Key classes:** Person, PostAssertion, RelationshipAssertion, StatusAssertion, DateInformation, Office, Province

### POMS
- **Source:** KDL CKAN — `https://data.kdl.kcl.ac.uk/dataset/people-of-medieval-scotland-project-1093-1371`
- **Format:** RDF (ZIP)
- **License:** TBD — resolve during implementation by checking CKAN metadata
- **URI namespace:** TBD — resolve during implementation by inspecting RDF dump
- **Key classes:** Person, factoid types, Document, Place — confirm against actual RDF

### Pleiades
- **Source:** `https://pleiades.stoa.org/downloads` (weekly Turtle dump)
- **Format:** Turtle (.ttl.gz)
- **Size:** ~41,480 places
- **License:** CC BY 3.0
- **Citable release:** v4.1 (Zenodo DOI: 10.5281/zenodo.1193921)
- **URI namespace:** `https://pleiades.stoa.org/places/`
- **Key classes:** `spatial:Feature`, `pleiades:Place`, `pleiades:Name`, `pleiades:Location`

### PeriodO
- **Source:** `http://n2t.net/ark:/99152/p0d.json`
- **Format:** JSON-LD (889 KB) — convert to Turtle via rdflib before loading
- **Size:** 9,017 periods, 273 authorities
- **License:** CC0 (public domain)
- **URI namespace:** `http://n2t.net/ark:/99152/`
- **Key classes:** `skos:Concept` (periods), `skos:ConceptScheme` (authorities)
- **Caveats:** Multiple definitions per period name (by design); structured dates are curator approximations

### Nomisma
- **Source:** `https://nomisma.org/data` (Turtle dumps)
- **Format:** Turtle
- **License:** CC BY (core concepts); partner datasets vary
- **URI namespace:** `http://nomisma.org/id/`
- **Key classes:** Concepts typed via `skos:Concept` — persons (`foaf:Person`), mints, denominations, materials
- **Scope for v1:** Core concept vocabulary only (not partner datasets like OCRE/CRRO)

## Scholarly References

### Foundational

- Bradley, J. & Short, H. (2005). "Texts into Databases: The Evolving Field of New-style Prosopography." *Literary and Linguistic Computing* 20 (Suppl), pp. 3-24.
- Pasin, M. & Bradley, J. (2015). "Factoid-based Prosopography and Computer Ontologies: Towards an Integrated Approach." *Digital Scholarship in the Humanities* 30(1), pp. 86-97.
- Bradley, J. (2020). Factoid Prosopography Ontology (FPO) v1.0. https://github.com/johnBradley501/FPO

### Pleiades

- Elliott, T. & Gillies, S. (2009). "Digital Geography and Classics." *Digital Humanities Quarterly* 3(1).
- Bagnall, R. et al. (eds.), *Pleiades: A Gazetteer of Past Places*. Zenodo DOI: 10.5281/zenodo.1193921.

### PeriodO

- Golden, P. & Shaw, R. (2016). "Nanopublication beyond the sciences: the PeriodO period gazetteer." *PeerJ Computer Science* 2:e44.
- Rabinowitz, A. et al. (2016). "Making Sense of the Ways We Make Sense of the Past." *Bulletin of the Institute of Classical Studies* 59(2): 42-55.

### Nomisma

- Gruber, E. & Meadows, A. (2021). "Numismatics and Linked Open Data." *ISAW Papers* 20.6.
- Hellings, B. (2024). "Review: Nomisma." *Reviews in Digital Humanities* 5(10).

### Cross-Linking

- Bodard, G. & Lawrence, F. (2014). "The SNAP:DRGN Project: Networking Ancient Prosopographies." DH2014.
- SNAP:DRGN Cookbook. https://github.com/SNAP-DRGN/Cookbook/wiki

## Known Caveats & Limitations

### Data Quality

- **DPRR:** Heavily senatorial/elite male; early Republic data inherits unreliable ancient traditions. Source: Broughton's MRR, with its inherited dating disputes.
- **Pleiades:** Coordinate accuracy varies (precise vs. rough). Pre-2016 entries may lack proper source citations. Coverage strongest for Greco-Roman Mediterranean.
- **PeriodO:** No single canonical period definition — multiple competing definitions by design. Structured dates are approximations of source text.
- **Nomisma:** Strongest for Greco-Roman coinage; medieval coverage sparse. Partner dataset coverage is uneven across institutions.
- **POMS:** Complex RDF structure; SPARQL queries require understanding charter-based evidence model.

### Linkage Limitations

- Curated linkages are necessarily incomplete — they cover the most obvious high-value mappings first
- Person-to-person links across datasets require scholarly judgment (name + date matching is unreliable for common Roman names)
- Place linkages are more straightforward (Pleiades IDs are widely used as stable identifiers)
- Period linkages are conceptually fuzzy (PeriodO's multiple-definition model means a DPRR date range may match several PeriodO periods)

### Technical Limitations

- All stores are read-only — no live data integration from remote SPARQL endpoints
- PeriodO JSON-LD → Turtle conversion may lose some JSON-LD framing context
- Embedding retrieval quality depends on the embedding model; domain-specific ancient world terms may not embed well with general-purpose models
- No SPARQL federation — each dataset is queried independently; cross-dataset joins happen at the application layer via the linkage graph

## Future Directions (Post-v1)

- **Additional dataset plugins** as RDF becomes available (PBW, PASE, CCEd, Charlemagne's Europe)
- **Agent-contributed linkages** — tool for scholars to assert new cross-references with provenance
- **Algorithmic link suggestion** — label similarity, temporal overlap, Wikidata hub matching
- **IPIF (International Prosopographical Interchange Format)** support for REST API access to web-only databases
- **Domain-specific embedding model** — fine-tune on ancient world terminology for better retrieval
- **Wikidata bridge** — many entities in these datasets have Wikidata QIDs; use as a linking hub
- **Trismegistos integration** — TM Person IDs as a cross-reference hub for ancient persons

### Pelagios Network Alignment

This project aligns closely with the [Pelagios Network](https://pelagios.org/) — a global community for linking heritage data using LOD. Key integration points:

- **Registry Working Group** — Pelagios catalogues LOD knowledge graphs and creates natural-language-question / SPARQL-query documentation pairs, which is exactly what our `examples.yaml` files provide. Contributing our question-SPARQL pairs to their registry would increase visibility and reuse.
- **Linked Places Format (LPF)** — Adding an LPF export capability for place-related query results would make our data consumable by Peripleo Lite and the World Historical Gazetteer.
- **PLATO ontology** (Place Attestation Ontology, Feb 2026) — A new Pelagios-developed ontology whose core unit is an attestation (a claim about a place from a source), conceptually identical to the factoid model. Aligning with PLATO would strengthen interoperability.
- **CHAI Cookbook** — Pelagios is actively exploring LLM + LOD integration (`pelagios/llm-lod-enriching-heritage`). An MCP server providing structured SPARQL access to ancient world datasets is a natural complement.
- **Membership** — Become a Pelagios Partner (officers@pelagios.org). Engage with the People Working Group (people@pelagios.org) and Registry Working Group (registry@pelagios.org). Present at Linked Pasts conference (December annually).
