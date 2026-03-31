# RDF Dataset Distribution via OCI: Convention Specification

**Date:** 2026-03-30
**Status:** Draft
**Package:** linked-past-store

## Problem

Scholarly RDF datasets need reliable, versioned, citable distribution. Current approaches — project websites, institutional servers, GitHub releases — suffer from link rot, missing metadata, inconsistent formats, and no standard for machine-readable provenance. Researchers citing a dataset URL today cannot guarantee the same bytes will be served tomorrow.

## Proposal

A convention for distributing RDF datasets as OCI (Open Container Initiative) artifacts, combining:

1. **Content-addressable storage** via OCI digests (SHA256 of exact bytes)
2. **Structured metadata** via OCI manifest annotations (flat, tool-accessible)
3. **RDF metadata** via VoID descriptions (queryable, interoperable)
4. **Sanitized, verified data** ready for strict parsers (Oxigraph, etc.)

## Artifact Structure

Each dataset is an OCI artifact with one or more data layers plus metadata layers:

```
OCI Artifact
├── Data layers: *.ttl              (application/x-turtle)
│   One or more RDF files, sanitized for strict parsers.
│   Single-file datasets have one layer. Multi-file datasets
│   (e.g., EDH with inscriptions, people, geography) preserve
│   their original file structure — one layer per file.
│
├── Metadata: void.ttl              (application/x-turtle)
│   VoID description of the dataset
│
├── Schema: ontology.ttl            (application/x-turtle, optional)
│   OWL/RDFS ontology if available
│
└── Manifest annotations
    ├── org.opencontainers.image.* (standard OCI)
    └── dev.linked-past.*          (domain-specific)
```

### Multi-File Datasets

Some datasets are naturally organized as multiple files (vocabularies, partitions by entity type, etc.). Rather than concatenating into a single blob — which loses provenance and makes selective loading impossible — each file is pushed as a separate OCI layer.

**Example: EDH (9 files)**
```
OCI Artifact: ghcr.io/gillisandrew/linked-past/edh:2026-03-30
├── edh_inscriptions.ttl          (66 MB, 70K inscriptions)
├── edh_people.ttl                (40 MB, 87K persons)
├── edh_geography_places.ttl      (13 MB, 30K places)
├── edh_material.ttl              (10 KB, vocabulary)
├── edh_type_of_inscription.ttl   (9 KB, vocabulary)
├── edh_type_of_monument.ttl      (8 KB, vocabulary)
├── edh_social_status.ttl         (2 KB, vocabulary)
├── edh_workstatus.ttl            (1 KB, vocabulary)
├── edh_contributor.ttl           (8 KB, vocabulary)
└── void.ttl                      (metadata)
```

**Example: Pleiades (11 files)**
```
OCI Artifact: ghcr.io/gillisandrew/linked-past/pleiades:2026-03-30
├── places-1.ttl through places-9.ttl  (data partitions)
├── place-types.ttl                    (vocabulary)
├── time-periods.ttl                   (vocabulary)
├── authors.ttl                        (vocabulary)
├── errata.ttl                         (corrections)
└── void.ttl                           (metadata)
```

**Example: DPRR (single file)**
```
OCI Artifact: ghcr.io/gillisandrew/linked-past/dprr:2026-03-30
├── dprr.ttl                      (35 MB, all data)
├── ontology.ttl                  (OWL ontology, optional)
└── void.ttl                      (metadata)
```

**Pushing multi-file artifacts with ORAS:**
```bash
oras push ghcr.io/myorg/edh:v1 \
  edh_inscriptions.ttl:application/x-turtle \
  edh_people.ttl:application/x-turtle \
  edh_geography_places.ttl:application/x-turtle \
  edh_material.ttl:application/x-turtle \
  edh_type_of_inscription.ttl:application/x-turtle \
  edh_type_of_monument.ttl:application/x-turtle \
  edh_social_status.ttl:application/x-turtle \
  edh_workstatus.ttl:application/x-turtle \
  edh_contributor.ttl:application/x-turtle \
  void.ttl:application/x-turtle \
  --annotation "org.opencontainers.image.licenses=CC-BY-SA-4.0" \
  --annotation "dev.linked-past.files=9" \
  --annotation "dev.linked-past.triples=1613841"
```

On pull, `oras pull` restores all files with original names. The plugin's `load()` method globs `*.ttl` and loads each file into the store.

**Benefits of keeping files separate:**
- **Provenance**: each file retains its original name and identity
- **Selective loading**: a consumer could load only vocabulary files for schema inspection without downloading the 66MB inscriptions file
- **Debugging**: if one file has parse errors, you know which one
- **Upstream alignment**: preserves the structure the dataset publisher intended
- **Layer-level caching**: OCI caches each layer by digest — if only the inscriptions file changes between versions, only that layer is re-downloaded

**Annotation for file count:**
The manifest annotation `dev.linked-past.files` records the number of data files (excluding void.ttl and ontology.ttl) so consumers know what to expect.

### Data Layer(s)

- Format: Turtle (`.ttl`)
- Encoding: UTF-8
- Sanitized: BCP 47 language tags valid, all IRIs have schemes, no invalid Unicode
- Verified: all files load cleanly into pyoxigraph (strictest common parser)
- Media type: `application/x-turtle`
- One layer per file for multi-file datasets; single layer for single-file datasets

### Layer 2: VoID Description

A Turtle file describing the dataset using the [VoID vocabulary](https://www.w3.org/TR/void/):

```turtle
@prefix void: <http://rdfs.org/ns/void#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<> a void:Dataset ;
    dcterms:title "Digital Prosopography of the Roman Republic (DPRR)" ;
    dcterms:description "Structured prosopography of the Roman Republic..." ;
    dcterms:license <https://creativecommons.org/licenses/by-nc/4.0/> ;
    dcterms:source <https://romanrepublic.ac.uk/> ;
    dcterms:created "2026-03-30"^^xsd:date ;

    # Dataset metrics
    void:triples 654125 ;
    void:entities 4876 ;
    void:classes 15 ;
    void:properties 42 ;

    # URI patterns
    void:uriSpace "http://romanrepublic.ac.uk/rdf/" ;
    void:exampleResource <http://romanrepublic.ac.uk/rdf/entity/Person/1957> ;

    # Distribution
    void:dataDump <https://ghcr.io/v2/gillisandrew/linked-past/dprr/blobs/sha256:...> ;
    void:sparqlEndpoint <http://127.0.0.1:8000/mcp> ;

    # Links to other datasets
    void:subset [
        a void:Linkset ;
        void:target <https://pleiades.stoa.org/> ;
        void:linkPredicate <http://www.w3.org/2004/02/skos/core#closeMatch> ;
        void:triples 5
    ] ;
    void:subset [
        a void:Linkset ;
        void:target <http://nomisma.org/> ;
        void:linkPredicate <http://www.w3.org/2004/02/skos/core#closeMatch> ;
        void:triples 187
    ] ;

    # Provenance
    dcterms:publisher [
        a foaf:Organization ;
        foaf:name "King's College London" ;
        foaf:homepage <https://romanrepublic.ac.uk/>
    ] ;

    # Citation
    dcterms:bibliographicCitation
        "Mouritsen et al., DPRR, King's Digital Lab, 2017. https://romanrepublic.ac.uk/" .
```

### Manifest Annotations

OCI manifest annotations mirror key VoID fields for flat lookup (no RDF parsing needed):

| Annotation | Source | Example |
|---|---|---|
| `org.opencontainers.image.title` | `dcterms:title` | `Digital Prosopography of the Roman Republic` |
| `org.opencontainers.image.description` | `dcterms:description` | `Structured prosopography...` |
| `org.opencontainers.image.licenses` | `dcterms:license` (SPDX) | `CC-BY-NC-4.0` |
| `org.opencontainers.image.source` | `dcterms:source` | `https://romanrepublic.ac.uk/` |
| `org.opencontainers.image.version` | version tag | `2026-03-30` |
| `org.opencontainers.image.created` | auto | `2026-03-30T14:22:00Z` |
| `org.opencontainers.image.vendor` | `dcterms:publisher` | `King's College London` |
| `dev.linked-past.dataset` | dataset ID | `dprr` |
| `dev.linked-past.format` | media type | `text/turtle` |
| `dev.linked-past.triples` | `void:triples` | `654125` |
| `dev.linked-past.uri-space` | `void:uriSpace` | `http://romanrepublic.ac.uk/rdf/` |
| `dev.linked-past.citation` | `dcterms:bibliographicCitation` | `Mouritsen et al., 2017` |
| `dev.linked-past.source-url` | original download URL | `https://...` |
| `dev.linked-past.sanitized` | sanitization applied | `rapper+regex` |
| `dev.linked-past.verified` | verification tool | `pyoxigraph` |

## VoID Generation

### Automatic (from data)

After loading into pyoxigraph, extract:

```python
triple_count = len(store)
classes = store.query("SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE { ?s a ?c }")
properties = store.query("SELECT (COUNT(DISTINCT ?p) AS ?n) WHERE { ?s ?p ?o }")
entities = store.query("SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE { ?s a ?type }")
uri_space = # common prefix of all subject URIs
example = store.query("SELECT ?s WHERE { ?s a ?type } LIMIT 1")
```

### From upstream VoID (enrich)

Some datasets publish VoID descriptions:

| Dataset | Upstream VoID |
|---|---|
| CRRO | `https://numismatics.org/crro/nomisma.void.rdf` |
| PeriodO | `https://data.perio.do/.well-known/void` |
| Nomisma | Via SPARQL endpoint |
| DPRR | None — generate |
| Pleiades | None — generate |
| EDH | None — generate |

When upstream VoID exists:
1. Fetch it
2. Update `void:triples` with our actual count (may differ after sanitization)
3. Add `void:dataDump` pointing to our OCI artifact
4. Preserve upstream `dcterms:publisher`, `dcterms:license`, etc.
5. Add linkset declarations for our cross-references

When no upstream VoID:
1. Generate entirely from data + plugin metadata (citation, license, source URL)

### Linkset Declarations

For each entry in the linkage graph, declare a `void:Linkset`:

```turtle
void:subset [
    a void:Linkset ;
    void:target <https://pleiades.stoa.org/> ;
    void:linkPredicate skos:closeMatch ;
    void:triples 5 ;
    dcterms:description "DPRR provinces linked to Pleiades places via Barrington Atlas"
] .
```

Count links per target dataset from the YAML files + Wikidata concordances.

## Pipeline

```
Upstream data (any RDF format)
        │
        ▼
   Sanitize (rapper pre-fix → rapper convert → regex post-fix)
        │
        ▼
   Verify (pyoxigraph bulk_load, count triples/classes/properties)
        │
        ▼
   Generate VoID (auto-extract metrics + enrich from upstream VoID + add linksets)
        │
        ▼
   Push to OCI registry
   ├── Layer 1: {dataset}.ttl
   ├── Layer 2: void.ttl
   ├── Annotations: mirror key VoID fields
   └── Digest: sha256:... (content-addressable citation anchor)
        │
        ▼
   Tag: {version} + latest
```

## Citing Artifacts

### For reproducibility (exact bytes):

```
DPRR RDF v2026-03-30
  ghcr.io/gillisandrew/linked-past/dprr@sha256:2aeecdfd3d99...
  654,125 triples. CC BY-NC 4.0.
```

### For human readability:

```
DPRR RDF v2026-03-30
  ghcr.io/gillisandrew/linked-past/dprr:2026-03-30
  See VoID: ghcr.io/gillisandrew/linked-past/dprr:2026-03-30 (void.ttl layer)
```

### In BibTeX:

```bibtex
@misc{dprr_rdf_2026,
  title     = {Digital Prosopography of the Roman Republic: RDF Dataset},
  author    = {Mouritsen, Henrik and Mayfield, Jamie and Bradley, John},
  year      = {2026},
  publisher = {King's Digital Lab, King's College London},
  note      = {Distributed via OCI: ghcr.io/gillisandrew/linked-past/dprr:2026-03-30,
               digest sha256:2aeecdfd3d99..., 654125 triples, CC BY-NC 4.0},
  url       = {https://romanrepublic.ac.uk/}
}
```

## Implementation in linked-past-store

### New module: `void.py`

```python
from linked_past_store.void import generate_void, enrich_void

# Generate from data + metadata
void_ttl = generate_void(
    data_path="dprr.ttl",
    dataset_id="dprr",
    title="Digital Prosopography of the Roman Republic",
    license_uri="https://creativecommons.org/licenses/by-nc/4.0/",
    source_uri="https://romanrepublic.ac.uk/",
    citation="Mouritsen et al., DPRR, 2017",
    publisher="King's College London",
)

# Enrich from upstream VoID
void_ttl = enrich_void(
    void_path="void.ttl",
    upstream_void_url="https://numismatics.org/crro/nomisma.void.rdf",
    actual_triple_count=54000,
)
```

### Updated push

```python
from linked_past_store import push_dataset

push_dataset(
    ref="ghcr.io/myorg/dataset:v1.0",
    data_path="data.ttl",
    void_path="void.ttl",  # NEW: optional VoID sidecar
    annotations={...},      # Auto-populated from VoID if not specified
)
```

### Updated CLI

```bash
# Generate VoID
linked-past-store void generate data.ttl --title "My Dataset" --license CC-BY-4.0

# Push with VoID
linked-past-store push ghcr.io/myorg/dataset:v1.0 data.ttl --void void.ttl

# Inspect VoID from a published artifact
linked-past-store void inspect ghcr.io/myorg/dataset:v1.0
```

## Scope

### v1

- `void.py` module: generate VoID from data metrics + metadata args
- Push with optional VoID sidecar layer
- Auto-extract: triple count, class count, property count, URI space, example resource
- Manifest annotations mirroring VoID fields
- CLI: `void generate`, push `--void`

### Future

- Fetch and merge upstream VoID
- Linkset declarations from linkage YAML
- VoID-of-VoID (discovery document listing all datasets)
- DCAT (Data Catalog Vocabulary) alignment for institutional catalogs
- Signposting headers for HTTP content negotiation on artifact URIs
- W3C PROV-O provenance chain (sanitization + verification steps)

## Potential Addition: Ontology-Aware Schema Generation

### Problem

Each dataset plugin requires a hand-written `schemas.yaml` that lists classes, properties, and ranges for SPARQL validation and schema display. This is error-prone, incomplete, and doesn't capture class hierarchy or property inheritance.

Some datasets publish formal OWL/RDFS ontologies (e.g., DPRR publishes a full OWL ontology with 30+ classes, domain/range declarations, and rich `rdfs:comment` annotations). Others only use predicates implicitly. The current approach treats both the same — manual YAML regardless.

### Proposed Solution

Add an optional **Layer 3: ontology.ttl** to the OCI artifact, plus an `ontology.py` module in `linked-past-store` that can extract schemas from either formal ontologies or empirical data analysis.

#### Artifact Structure (Extended)

```
OCI Artifact
├── Layer 1: {dataset}.ttl          (application/x-turtle)     — data
├── Layer 2: void.ttl               (application/x-turtle)     — dataset metadata
├── Layer 3: ontology.ttl           (application/x-turtle)     — schema (optional)
└── Manifest annotations
```

Layer 3 is the dataset's ontology — either the upstream OWL/RDFS file (if published) or an auto-generated schema extracted from the data.

#### Schema Extraction Pipeline

```
Has ontology file?
  │
  ├─ YES → Parse OWL/RDFS
  │        Extract: classes, properties, domains, ranges, hierarchy, comments
  │        Output: complete, authoritative schema
  │
  └─ NO  → Empirical extraction from data
           Query: SELECT ?class ?pred (COUNT(*) AS ?n) WHERE { ?s a ?class ; ?pred ?o }
           Output: de facto schema (what's actually used)
           Note: may miss abstract classes, won't have hierarchy or comments
  │
  ▼
Generate schemas.yaml (for runtime validation)
Generate schema docs (for get_schema tool display)
Enrich VoID with class/property counts
```

#### What Formal Ontology Parsing Provides

Using the DPRR ontology as an example:

**Class hierarchy:**
```
ThingWithID
├── ThingWithName
│   ├── Person
│   └── AuthorityList
│       ├── AuthorityWithAbbreviation
│       │   ├── Office
│       │   ├── Praenomen
│       │   └── Status
│       └── AuthorityWithDescription
├── Assertion
│   ├── AssertionWithDateRange
│   │   ├── PostAssertion
│   │   └── StatusAssertion
│   ├── RelationshipAssertion
│   ├── TribeAssertion
│   └── DateInformation
└── NoteContainer
    ├── Note
    └── NoteForProvince
        ├── PostAssertionProvince
        └── StatusAssertionProvince
```

**Property inheritance:** `isUncertain` is declared on `Assertion` with `rdfs:domain :Assertion`. This means it's valid on all 6+ assertion subclasses — something our hand-written `schemas.yaml` doesn't express. A validator that understands hierarchy can correctly allow `isUncertain` on a `TribeAssertion` without listing it explicitly.

**Rich comments as documentation:** Every class and property has `rdfs:comment` from the ontology author. These are better than our hand-written one-liners:

```
:PostAssertion rdfs:comment "provides a mechanism that a DPRR person held
  a particular office at a particular date or date range."

:isUncertain rdfs:comment "When true, specifies that the information in
  the Assertion is uncertain. Only appears if 'true'."
```

These comments can directly populate the `get_schema` tool output and the schema descriptions in VoID.

#### What Empirical Extraction Provides (Fallback)

For datasets without ontologies (EDH, Pleiades, Nomisma), query the loaded store:

```sparql
# Classes by usage
SELECT ?class (COUNT(DISTINCT ?s) AS ?instances)
WHERE { ?s a ?class }
GROUP BY ?class ORDER BY DESC(?instances)

# Properties per class
SELECT ?class ?pred (SAMPLE(?o) AS ?example) (COUNT(*) AS ?usage)
WHERE { ?s a ?class ; ?pred ?o }
GROUP BY ?class ?pred ORDER BY ?class DESC(?usage)

# Infer ranges from actual values
SELECT ?pred (DATATYPE(?o) AS ?range) (COUNT(*) AS ?n)
WHERE { ?s ?pred ?o . FILTER(isLiteral(?o)) }
GROUP BY ?pred ?range
```

This produces:
- List of all classes with instance counts
- Properties used on each class with usage frequency
- Inferred ranges from literal datatypes
- Example values for documentation

Missing compared to formal ontology:
- No class hierarchy (flat list)
- No abstract classes (only instantiated ones)
- No `rdfs:comment` documentation
- Inferred ranges may be noisy (multiple datatypes per property)

#### Implementation in `linked-past-store`

```python
# linked_past_store/ontology.py

def extract_from_ontology(ontology_path: Path) -> Schema:
    """Parse OWL/RDFS ontology file. Returns complete schema with hierarchy."""

def extract_from_data(store: Store) -> Schema:
    """Empirical schema extraction from loaded RDF data. Best-effort fallback."""

def generate_schemas_yaml(schema: Schema, output_path: Path) -> None:
    """Write schema to YAML format compatible with linked-past plugin context."""

def extract_schema(
    data_path: Path | None = None,
    ontology_path: Path | None = None,
) -> Schema:
    """Extract schema from ontology (preferred) or data (fallback)."""
```

#### CLI

```bash
# From ontology file
linked-past-store ontology extract ontology.ttl --output schemas.yaml

# From data (empirical)
linked-past-store ontology extract --from-data dataset.ttl --output schemas.yaml

# Both (ontology + data counts for VoID)
linked-past-store ontology extract ontology.ttl --enrich-from dataset.ttl --output schemas.yaml
```

#### Interaction with Existing Components

| Component | Current | With Ontology |
|---|---|---|
| `schemas.yaml` | Hand-written | Auto-generated (ontology or empirical) |
| `tips.yaml` | Hand-written | Hand-written (domain expertise, not extractable) |
| `examples.yaml` | Hand-written | Hand-written (pedagogical, not extractable) |
| `prefixes.yaml` | Hand-written | Auto-extractable from ontology `@prefix` declarations |
| Validation | Flat class→property map | Hierarchy-aware (property valid on class or any ancestor) |
| `get_schema` | Renders YAML | Renders YAML + ontology comments |
| VoID | Class/property counts | Counts + hierarchy depth + comment excerpts |

#### Heterogeneous Dataset Support

| Dataset | Ontology Available | Strategy |
|---|---|---|
| DPRR | Full OWL (published by Bradley) | Parse ontology → authoritative schema |
| Nomisma | NMO OWL (published at nomisma.org/ontology) | Parse ontology → authoritative schema |
| EDH | RDFS classes in vocabulary files | Parse RDFS → partial schema + empirical enrichment |
| Pleiades | RDFS vocab (published at pleiades.stoa.org/places/vocab) | Parse RDFS → partial schema + empirical enrichment |
| PeriodO | SHACL shapes (published at data.perio.do) | Parse SHACL → constraint-based schema (different approach) |
| CRRO/OCRE | Uses NMO (same as Nomisma) | Inherit from Nomisma schema |

The key insight: **parse what's available, fall back to empirical, layer human curation on top.** The three layers (ontology → data → human) complement each other.

## Design Principles

1. **Annotations are the index, VoID is the authority.** OCI annotations provide fast flat lookup. VoID provides the full queryable description. They should agree; if they diverge, VoID wins.

2. **Generate, don't require.** Not all upstream datasets publish VoID. The tool should generate useful VoID from any RDF file + minimal metadata (title, license).

3. **Content-addressable citation.** Every artifact has a digest. Scholarly citations should include it for reproducibility.

4. **Separation of data and metadata.** Data is Layer 1, metadata is Layer 2. You can pull just the VoID to inspect a dataset without downloading the data.

5. **Compatible with existing conventions.** VoID is a W3C Interest Group Note (2011). OCI annotations follow the OCI image spec. No new vocabulary invented.
