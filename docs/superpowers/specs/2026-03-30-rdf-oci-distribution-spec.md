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

Each dataset is an OCI artifact with two layers:

```
OCI Artifact
├── Layer 1: {dataset}.ttl          (application/x-turtle)
│   The RDF data, serialized as Turtle, sanitized for strict parsers
│
├── Layer 2: void.ttl               (application/x-turtle)
│   VoID description of the dataset
│
└── Manifest annotations
    ├── org.opencontainers.image.* (standard OCI)
    └── dev.linked-past.*          (domain-specific)
```

### Layer 1: Data

- Format: Turtle (`.ttl`)
- Encoding: UTF-8
- Sanitized: BCP 47 language tags valid, all IRIs have schemes, no invalid Unicode
- Verified: loads cleanly into pyoxigraph (strictest common parser)
- Media type: `application/x-turtle`

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

## Design Principles

1. **Annotations are the index, VoID is the authority.** OCI annotations provide fast flat lookup. VoID provides the full queryable description. They should agree; if they diverge, VoID wins.

2. **Generate, don't require.** Not all upstream datasets publish VoID. The tool should generate useful VoID from any RDF file + minimal metadata (title, license).

3. **Content-addressable citation.** Every artifact has a digest. Scholarly citations should include it for reproducibility.

4. **Separation of data and metadata.** Data is Layer 1, metadata is Layer 2. You can pull just the VoID to inspect a dataset without downloading the data.

5. **Compatible with existing conventions.** VoID is a W3C Interest Group Note (2011). OCI annotations follow the OCI image spec. No new vocabulary invented.
