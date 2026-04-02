# RFC: OCI-Based Distribution of Linked Open Data

**Status:** Draft
**Authors:** Andrew Gillis
**Date:** 2026-04-02

## Abstract

We propose using OCI (Open Container Initiative) registries as a distribution mechanism for Linked Open Data (LOD) datasets. By packaging RDF datasets as OCI artifacts — with content-addressable layers, immutable versioning, and standardized metadata — we address persistent shortcomings in LOD distribution: unreliable SPARQL endpoints, unversioned data dumps, poor discoverability, and lack of integrity verification. This approach builds on existing infrastructure (container registries, ORAS tooling) and complements established Semantic Web standards (VoID, DCAT, RDFC-1.0).

## 1. Problem Statement

The Linked Open Data ecosystem has well-documented distribution problems that have persisted for over a decade.

### 1.1 SPARQL Endpoint Fragility

The dominant access method for LOD — public SPARQL endpoints — is unreliable at scale. Buil-Aranda et al. (2013) monitored 427 public endpoints over 27 months and found that only **32.2% achieved 99–100% availability**. Performance varied by 3–4 orders of magnitude across endpoints, and only one-third provided discoverable metadata. The SPARQLES monitoring project (Vandenbussche et al., 2017) confirmed these findings with ongoing probing: endpoints go down, change URLs, or degrade without notice.

For scholarly applications — where a query executed today must be reproducible next year — this is untenable.

### 1.2 Data Dump Limitations

Bulk data dumps (gzipped Turtle, N-Triples, RDF/XML) are the fallback when endpoints fail. But they lack:

- **Versioning** — No standard mechanism to track which version of a dataset was used. Most dumps are overwritten in place at a single URL.
- **Incremental updates** — Consumers must re-download the entire dataset even if only a few triples changed.
- **Integrity verification** — Until RDFC-1.0 (W3C Recommendation, 2024), there was no standard way to verify that a downloaded dataset matched what the publisher intended. Even now, adoption is minimal.
- **Metadata co-location** — License, provenance, citation, and structural statistics are typically published separately from the data (if at all), leading to metadata loss during distribution.
- **Discoverability** — Finding whether a dataset exists, what version is current, and where to download it requires consulting external catalogs (LOD Cloud, DCAT portals) that are themselves incomplete.

### 1.3 The Quality Gap

The LOD Laundromat project (Beek et al., 2014) found that the majority of published LOD datasets do not meet basic publishing guidelines. A 2024 analysis of 1,658 LOD Cloud datasets found persistent quality problems, concluding that well-curated, regularly maintained datasets remain the exception (Pellegrino et al., 2024). Datasets accumulate encoding errors, broken IRIs, and stale links over time, with no standard pipeline for cleaning and republishing.

### 1.4 Scholarly Reproducibility

For digital humanities and computational archaeology — the domain that motivated this work — reproducibility requires:

1. Pinning the exact version of each dataset used in an analysis
2. Verifying data integrity (the bits haven't changed)
3. Citing the dataset with version, license, and provenance
4. Re-running queries against the same data years later

No current LOD distribution method satisfies all four requirements.

## 2. Prior Art

Several projects have addressed pieces of the distribution problem:

| Approach | Addresses | Limitations |
|----------|-----------|-------------|
| **HDT** (Fernandez et al., 2013) | Compression, queryable binary format | No versioning, no registry infrastructure, single-file distribution |
| **Triple Pattern Fragments** (Verborgh et al., 2016) | Endpoint availability via client-side query processing | Requires running a server; no offline/archival use case |
| **LOD Laundromat** (Beek et al., 2014) | Uniform cleaning and republishing | Centralized; single point of failure; project eventually went offline |
| **DCAT v3** (W3C, 2024) | Federated discovery via metadata catalogs | Catalog only — doesn't address the distribution mechanism itself |
| **VoID** (W3C, 2011) | Dataset-level statistics and linksets | Metadata vocabulary, not a distribution format |
| **RDFC-1.0** (W3C, 2024) | Content-addressable hashing of RDF graphs | Integrity primitive — no packaging or distribution mechanism |
| **RO-Crate** (Soiland-Reyes et al., 2022) | Research artifact packaging with JSON-LD metadata | File-level packaging; no registry infrastructure or layer-level deduplication |
| **Zenodo/Figshare** | DOIs, versioning, long-term archival | General-purpose; no RDF-specific tooling; no incremental downloads |
| **KitOps / OMLMD** (CNCF, 2024–2025) | OCI-based packaging of ML models and training datasets | ML-domain-specific; no RDF or Semantic Web metadata integration |
| **OSTRICH** (Taelman et al., 2018) | Versioned RDF storage via HDT snapshots + delta chains | Archival/query system, not a distribution mechanism |

The ML ecosystem has begun using OCI registries for model and dataset distribution (KitOps entered the CNCF Sandbox in 2025), demonstrating the viability of OCI for non-container artifacts at scale. However, no published work has applied this approach specifically to RDF datasets with Semantic Web metadata integration (VoID, PROV-O, RDFC-1.0). None of the above provides a complete solution combining: versioned distribution, content-addressable integrity, incremental updates, co-located Semantic Web metadata, and standard registry infrastructure.

## 3. Proposed Approach: OCI Artifacts for LOD

### 3.1 OCI Registries as Distribution Infrastructure

The Open Container Initiative (OCI) defines standards for container images and their distribution. A key insight is that the OCI distribution spec is **content-type agnostic** — it distributes content-addressable blobs organized into manifests, regardless of what those blobs contain. Container images are the primary use case, but the same infrastructure supports any artifact type.

OCI registries (GitHub Container Registry, Docker Hub, Amazon ECR, Harbor, etc.) are:

- **Globally distributed** with CDN-backed pull
- **Content-addressable** — every blob identified by its SHA-256 digest
- **Immutably versioned** — tags point to manifest digests; digests never change
- **Access-controlled** — per-repository authentication and authorization
- **Highly available** — major registries offer 99.9%+ uptime SLAs
- **Currently free for public artifacts** — GitHub Container Registry provides free public image storage (subject to policy changes with 30 days notice; 10 GB per-layer limit)

The ORAS (OCI Registry As Storage) project provides CLI and client libraries for pushing and pulling non-container artifacts to OCI registries, already used in production for Helm charts, WebAssembly modules, SBOMs, policy bundles, and ML models.

### 3.2 LOD Dataset as OCI Artifact

We propose packaging each LOD dataset as a multi-layer OCI artifact:

```
ghcr.io/publisher/lod/{dataset}:{version}
  │
  ├─ Layer 1: {dataset}.ttl          (RDF data, text/turtle)
  ├─ Layer 2: _void.ttl              (VoID metadata)
  ├─ Layer 3: _schema.yaml           (Extracted ontology / shapes)
  ├─ Layer 4: _ontology.ttl          (Bundled external ontology, optional)
  │
  └─ Manifest annotations:
       org.opencontainers.image.licenses: "CC-BY-4.0"
       org.opencontainers.image.source: "https://source.example.org"
       org.opencontainers.image.created: "2026-04-01T12:00:00Z"
       dev.lod.triples: "427281"
       dev.lod.format: "text/turtle"
       dev.lod.citation: "Author (Year). Title. URL."
       dev.lod.void-digest: "sha256:abc123..."
```

### 3.3 Properties Achieved

| Property | How OCI achieves it |
|----------|-------------------|
| **Versioning** | Immutable tags (`:latest`, `:v2.1`) pointing to manifest digests. Previous versions remain accessible by digest. |
| **Integrity** | Every layer is content-addressed (SHA-256). Pull verifies digests automatically. Complements RDFC-1.0 for graph-level integrity. |
| **Incremental updates** | Layer-level deduplication: if only the VoID metadata changes between versions, only that layer is re-downloaded. Data layers (often 90%+ of artifact size) are cached. |
| **Co-located metadata** | License, citation, provenance, and structural statistics travel with the data as manifest annotations and sidecar layers. No metadata loss during distribution. |
| **Discoverability** | Standard OCI registry APIs for listing tags, fetching manifests, and reading annotations. Enables catalog-building without downloading data. |
| **Offline use** | Pull once, use forever. No dependency on endpoint availability. |
| **Reproducibility** | Pin to manifest digest (`@sha256:...`) for bitwise-identical reproduction. |
| **Global distribution** | Leverage existing CDN infrastructure of major registries. |

### 3.4 Layer Convention

We propose a layer naming convention for RDF dataset artifacts:

| Layer filename | Media type | Required | Purpose |
|---------------|-----------|----------|---------|
| `{name}.ttl` | `text/turtle` | Yes | Primary RDF data |
| `_void.ttl` | `text/turtle` | Recommended | VoID dataset description |
| `_schema.yaml` | `application/x-yaml` | Optional | Extracted class/property schema |
| `_ontology.ttl` | `text/turtle` | Optional | Bundled ontology for inference |
| `_shacl.ttl` | `text/turtle` | Optional | SHACL shapes for validation |

The `_` prefix distinguishes metadata sidecars from data files. Multi-file datasets (e.g., sharded by entity type) use multiple data layers without the prefix.

### 3.5 Manifest Annotations

We propose a namespace for RDF-specific OCI manifest annotations, building on the OCI image spec's annotation keys:

| Annotation key | Value | Source |
|---------------|-------|--------|
| `org.opencontainers.image.licenses` | SPDX identifier | OCI spec |
| `org.opencontainers.image.source` | Upstream source URL | OCI spec |
| `org.opencontainers.image.created` | ISO 8601 timestamp | OCI spec |
| `dev.lod.format` | MIME type (e.g., `text/turtle`) | Proposed |
| `dev.lod.triples` | Triple count (string) | Proposed |
| `dev.lod.classes` | Number of distinct classes | Proposed |
| `dev.lod.citation` | Plain-text citation string | Proposed |
| `dev.lod.void-digest` | SHA-256 of VoID sidecar | Proposed |
| `dev.lod.canonical-digest` | RDFC-1.0 canonical hash | Proposed |

## 4. Pipeline Architecture

A complete LOD distribution pipeline using OCI:

```
Publisher                        OCI Registry                    Consumer
─────────                        ────────────                    ────────

  Upstream    ┌──────────┐    ┌──────────────┐    ┌──────────┐
  source  ──→ │  Ingest  │──→ │  raw/{name}  │    │   Pull   │
              └──────────┘    │  :latest     │    │  (ORAS)  │
                              └──────┬───────┘    └────┬─────┘
                                     │                  │
                              ┌──────┴───────┐    ┌────┴─────┐
                              │   Sanitize   │    │  Verify  │
                              │   + VoID     │    │  + Load  │
                              │   + Schema   │    │  + Index │
                              └──────┬───────┘    └──────────┘
                                     │
                              ┌──────┴───────┐
                              │  datasets/   │
                              │  {name}:     │
                              │  latest      │
                              └──────────────┘
```

### 4.1 Publisher Workflow

1. **Ingest** — Fetch from upstream, normalize to Turtle, push as raw artifact
2. **Clean** — Pull raw, sanitize (encoding fixes, blank node normalization), verify, generate VoID + schema
3. **Publish** — Push clean artifact with sidecars and annotations
4. **Tag** — Optionally tag with semantic version (`v2025.04`)

### 4.2 Consumer Workflow

1. **Discover** — Query registry API for available datasets and their annotations
2. **Pull** — Download artifact (layer-cached; only new/changed layers transfer)
3. **Verify** — Check layer digests (automatic) and optionally RDFC-1.0 canonical hash
4. **Load** — Bulk-load into local triplestore; apply ontology sidecars; materialize inferences
5. **Pin** — Record manifest digest in research outputs for reproducibility

## 5. Comparison with Existing Approaches

```
                    Versioned  Incremental  Integrity  Metadata   Offline  Discoverable
                                Updates     Verified   Co-located
────────────────────────────────────────────────────────────────────────────────────────
SPARQL Endpoint        ✗          N/A         ✗          ✗         ✗         △
Data Dump (HTTP)       ✗          ✗           ✗          ✗         ✓         ✗
HDT                    △¹         ✗           ✗          △         ✓         ✗
LOD Laundromat         ✗          ✗           ✓          ✓         ✓         ✓
Zenodo/Figshare        ✓          ✗²          ✓          ✓         ✓         ✓
RO-Crate               ✓          ✗           △          ✓         ✓         △
KitOps (ML/OCI)        ✓          ✓           ✓          △         ✓         ✓
OCI Artifact (this)    ✓          ✓³          ✓          ✓         ✓         ✓
```

¹ HDT itself has no versioning, but OSTRICH (Taelman et al., 2018) layers versioning on HDT snapshots with delta chains.
² Zenodo deduplicates storage internally across versions, but consumers must download whole files — no incremental transfer.
³ Incremental updates operate at **layer granularity**, not triple-level. If the main data file changes at all, the entire data layer re-downloads. The benefit is strongest when metadata sidecars change independently of the data.

The key differentiator is **incremental updates via layer-level deduplication** combined with **co-located Semantic Web metadata** — the combination is unique to this approach.

## 6. Implementation Status

This proposal is implemented and in production use as the `linked-past-store` Python package, distributing 7 ancient world datasets (DPRR, Pleiades, PeriodO, Nomisma, CRRO, OCRE, EDH) totaling ~4M triples via GitHub Container Registry.

**Source:** [github.com/gillisandrew/linked-past](https://github.com/gillisandrew/linked-past)

Implementation components:
- `push_dataset()` — Push RDF + sidecars as multi-layer OCI artifact
- `pull_for_dataset()` — Pull with layer-level caching and change detection
- `ArtifactCache` — Content-addressable local cache tracking per-manifest layer digests
- `generate_void()` — VoID metadata generation
- `extract_schema()` — Automatic class/property extraction
- `sanitize_turtle()` — RDF normalization (encoding fixes, blank nodes)
- `verify_turtle()` — RDF integrity verification

## 7. Attestation Model: Lessons from Software Supply Chain Security

The software supply chain faces remarkably parallel challenges to LOD distribution. The OCI ecosystem has developed a sophisticated attestation model to address them. We propose adapting this model for RDF datasets.

### 7.1 Parallel Problems

| Software Supply Chain | LOD Distribution | OCI Solution |
|----------------------|------------------|-------------|
| Is this the binary CI built? | Is this the dataset the publisher released? | Content-addressed digests (`sha256:...`) |
| What packages are inside? (SBOM) | What classes/properties are inside? (VoID) | Sidecar artifacts via referrers API |
| Who built it and from what source? (SLSA provenance) | Who transformed it and from what upstream? (PROV-O) | Attestation manifests with `subject` field |
| Does it have known vulnerabilities? (Trivy scan) | Does it meet quality thresholds? (Validation report) | Quality report as referrer artifact |
| Pin exact version in lockfile | Pin exact dataset for reproducibility | Manifest digest (`@sha256:...`) |
| npm/PyPI outage breaks builds | SPARQL endpoint goes down | Local pull + offline use |

### 7.2 The OCI Referrers API

OCI Distribution Spec v1.1 introduced a mechanism for artifacts to **reference** other artifacts. Any OCI manifest can include a `subject` field pointing to another manifest's digest. The registry's Referrers API (`GET /v2/<name>/referrers/<digest>`) returns all manifests that reference a given artifact, filterable by `artifactType`.

This is how the software ecosystem attaches signatures (Cosign), SBOMs (SPDX/CycloneDX), provenance (SLSA), and vulnerability scan results to container images — without modifying the original image.

### 7.3 Proposed LOD Referrer Types

We propose five referrer artifact types for RDF datasets:

**A. VoID Description** (analogous to SBOM)

```
Manifest:
  subject:      sha256:<dataset-digest>
  artifactType: application/vnd.w3.void+turtle
  layers:       [void.ttl]
  annotations:
    dev.lod.void.triples: "650000"
    dev.lod.void.classes: "12"
```

Consumers query: `GET /v2/.../referrers/<digest>?artifactType=application/vnd.w3.void+turtle`

Like an SBOM enumerating a container's packages, the VoID description enumerates a dataset's classes, properties, partitions, and linksets — enabling discovery and assessment without downloading the data.

**B. RDFC-1.0 Integrity Hash** (analogous to Cosign signature)

```
Manifest:
  subject:      sha256:<dataset-digest>
  artifactType: application/vnd.w3.rdfc1+json
  layers:       [{ "algorithm": "rdfc-1.0-sha256", "hash": "<canonical-hash>" }]
```

OCI digests verify byte-level integrity (same serialization → same hash). RDFC-1.0 verifies **graph-level** integrity (same triples → same hash, regardless of serialization order or blank node labeling). This is the RDF analog of a Cosign signature — it attests that the semantic content is what the publisher intended.

**C. PROV-O Provenance** (analogous to SLSA provenance)

```
Manifest:
  subject:      sha256:<dataset-digest>
  artifactType: application/vnd.w3.prov+turtle
  layers:       [provenance.ttl]
```

The provenance record captures the full derivation chain using PROV-O:

```turtle
<#activity> a prov:Activity ;
    prov:wasAssociatedWith <#pipeline> ;
    prov:used <upstream-source-url> ;
    prov:startedAtTime "2026-04-01T12:00:00Z" ;
    prov:generated <dataset-artifact-digest> .

<dataset-artifact-digest> a prov:Entity ;
    prov:wasDerivedFrom <upstream-source-url> ;
    prov:wasGeneratedBy <#activity> .
```

This parallels SLSA provenance (builder identity, source inputs, build parameters) but uses the W3C PROV ontology native to the Semantic Web.

**D. Data Quality Report** (analogous to vulnerability scan)

```
Manifest:
  subject:      sha256:<dataset-digest>
  artifactType: application/vnd.lod.quality-report+json
  layers:       [{
    "triple_count": 650000,
    "min_threshold": 600000,
    "schema_conformance": { "known_classes": 24, "unknown_classes": 7 },
    "broken_uris": 0,
    "encoding_fixes": 0,
    "validation_passed": true,
    "timestamp": "2026-04-01T12:00:00Z"
  }]
```

Like a Trivy vulnerability scan attached to a container image, quality reports document whether the dataset meets publishing standards. Consumers can make trust decisions based on these reports without loading the data.

**E. Linkset Declaration** (analogous to dependency manifest)

```
Manifest:
  subject:      sha256:<dataset-digest>
  artifactType: application/vnd.w3.void.linkset+turtle
  layers:       [dprr-nomisma-links.ttl]
  annotations:
    dev.lod.void.target: "ghcr.io/publisher/lod/nomisma:latest"
    dev.lod.void.triples: "1200"
```

Linksets describe connections between datasets — the LOD equivalent of a software dependency. By storing them as referrer artifacts, consumers discover inter-dataset relationships automatically when they pull a dataset.

### 7.4 Discovery Flow

```
Consumer pulls dataset artifact
        │
        ▼
GET /v2/.../referrers/<digest>
        │
        ├─ artifactType=void     → VoID description (what's inside?)
        ├─ artifactType=rdfc1    → Integrity hash (is it authentic?)
        ├─ artifactType=prov     → Provenance (where did it come from?)
        ├─ artifactType=quality  → Quality report (is it clean?)
        └─ artifactType=linkset  → Linksets (what does it connect to?)
```

This mirrors how Docker Scout discovers SBOMs, Cosign discovers signatures, and Trivy discovers scan results — all via the same referrers API, differentiated by `artifactType`.

### 7.5 Trust Levels (Inspired by SLSA)

We can define LOD Supply Chain Levels analogous to SLSA:

| Level | Requirements |
|-------|-------------|
| **L0** | Dataset published as OCI artifact with manifest annotations (license, source URL) |
| **L1** | VoID description and quality report attached as referrer artifacts |
| **L2** | RDFC-1.0 integrity hash attached; provenance record with pipeline identity |
| **L3** | Provenance generated by a trusted, isolated pipeline (CI/CD); cryptographic signature on the integrity hash |

## 8. Open Questions (Updated)

1. **Media types** — Should we register a dedicated OCI artifact media type for RDF datasets (e.g., `application/vnd.w3.rdf.dataset.v1+json` for the manifest config), or reuse the generic artifact type?

2. **Graph-level integrity** — RDFC-1.0 canonicalization enables graph-level (not just byte-level) integrity checking. Should the canonical digest be computed at publish time and included as a manifest annotation?

3. **Federation** — How should cross-registry distribution work? OCI registries support replication, but there's no standard for LOD-specific catalog federation on top of OCI.

4. **DCAT integration** — Should OCI manifests reference DCAT catalog entries, or should DCAT catalogs reference OCI artifacts as distributions? Both directions seem useful.

5. **Vocabulary convergence** — The `dev.lod.*` annotation namespace is proposed here. Standardization would require community consensus and potentially W3C coordination.

6. **Compression** — OCI layers support gzip compression. For large datasets (100M+ triples), should we standardize on compressed layers, or rely on registry-level transfer compression?

7. **Named graphs** — The current proposal treats each artifact as a single default graph. Multi-graph datasets (e.g., with provenance in named graphs) would need a convention for graph-layer mapping.

8. **Referrer adoption** — The OCI Referrers API (v1.1) is supported by GHCR, ECR, and Harbor, but not all registries. Should the proposal require referrers support, or include a fallback tag-based scheme (as Cosign does)?

9. **Signing** — Should LOD artifacts be signed using Sigstore/Cosign? This would provide non-repudiation (the publisher provably published this exact dataset). The infrastructure exists but adds tooling requirements.

10. **Scalability** — The current implementation distributes datasets of ~4M triples (~26 MB Turtle). For very large datasets (Wikidata: 18B+ triples, DBpedia: 2B+), single-file layers may hit registry limits (GHCR: 10 GB per layer, 10-minute upload timeout). Sharding strategies (by entity type, by named graph, or by partition) would need a layer-naming convention.

11. **Registry migration** — While OCI registries are interoperable in theory, migrating artifacts between registries (e.g., GHCR → Harbor) requires updating all consumer configurations. Multi-registry mirroring strategies should be considered for critical datasets.

### FAIR Principles Alignment

The proposed approach maps well to the FAIR principles (Wilkinson et al., 2016):

| Principle | How OCI artifacts satisfy it |
|-----------|----------------------------|
| **F1** (Globally unique identifier) | OCI manifest digests (`sha256:...`) are globally unique, persistent, content-addressed identifiers |
| **F2** (Rich metadata) | Manifest annotations carry license, citation, provenance; VoID sidecars carry structural statistics |
| **F3** (Metadata references data) | VoID and provenance referrer artifacts contain the dataset's manifest digest |
| **A1** (Retrievable by identifier) | Standard OCI pull by digest or tag; no custom protocol needed |
| **A2** (Metadata accessible even when data isn't) | Manifest annotations and referrer artifacts are accessible via registry API without pulling data layers |
| **I1** (Formal, shared knowledge representation) | RDF/Turtle with standard vocabularies (VoID, PROV-O, DCAT) |
| **I2** (Uses FAIR vocabularies) | VoID and PROV-O are W3C standards |
| **R1** (Rich provenance) | PROV-O provenance as referrer artifact; SLSA-inspired trust levels |

The main gap is **F4** (registered in a searchable resource) — OCI registries support tag listing and manifest inspection but lack the federated search capabilities of DCAT catalogs. Bridging OCI manifests to DCAT distributions (Open Question #4) would close this gap.

## 9. References

### SPARQL Endpoint Availability
- Buil-Aranda, C., Hogan, A., Umbrich, J., Vandenbussche, P.-Y. (2013). "SPARQL Web-Querying Infrastructure: Ready for Action?" *ISWC 2013*, LNCS 8219. [DOI: 10.1007/978-3-642-41338-4_18](https://link.springer.com/chapter/10.1007/978-3-642-41338-4_18)
- Vandenbussche, P.-Y., Umbrich, J., Matteis, L., Hogan, A., Buil-Aranda, C. (2017). "SPARQLES: Monitoring Public SPARQL Endpoints." *Semantic Web Journal* 8(6). [DOI: 10.3233/SW-170254](https://doi.org/10.3233/SW-170254)

### LOD Quality and Distribution
- Beek, W., Rietveld, L., Bazoobandi, H.R., Wielemaker, J., Schlobach, S. (2014). "LOD Laundromat: A Uniform Way of Publishing Other People's Dirty Data." *ISWC 2014*, LNCS 8796, pp. 213–228. [DOI: 10.1007/978-3-319-11964-9_14](https://doi.org/10.1007/978-3-319-11964-9_14)
- Pellegrino, M.A., Rula, A., Tuozzo, G. (2024). "Lost in LOD: Analyzing the Linked Open Data Cloud Quality Maze." *ACM Journal of Data and Information Quality*. [DOI: 10.1145/3786331](https://doi.org/10.1145/3786331)

### Formats and Interfaces
- Fernandez, J.D., Martinez-Prieto, M.A., Gutierrez, C., Polleres, A., Arias, M. (2013). "Binary RDF Representation for Publication and Exchange (HDT)." *Journal of Web Semantics* 19:22–41. [DOI: 10.1016/j.websem.2013.01.002](https://doi.org/10.1016/j.websem.2013.01.002)
- Verborgh, R., et al. (2016). "Triple Pattern Fragments: a Low-cost Knowledge Graph Interface for the Web." *Journal of Web Semantics* 37–38:184–206. [Author page](https://ruben.verborgh.org/publications/verborgh_jws_2016/)

### W3C Specifications
- DCAT v3. W3C Recommendation, 2024. [https://www.w3.org/TR/vocab-dcat-3/](https://www.w3.org/TR/vocab-dcat-3/)
- VoID. W3C Interest Group Note, 2011. [https://www.w3.org/TR/void/](https://www.w3.org/TR/void/)
- RDF Dataset Canonicalization (RDFC-1.0). W3C Recommendation, 2024. [https://www.w3.org/TR/rdf-canon/](https://www.w3.org/TR/rdf-canon/)
- SPARQL 1.1 Service Description. W3C Recommendation, 2013. [https://www.w3.org/TR/sparql11-service-description/](https://www.w3.org/TR/sparql11-service-description/)

### FAIR Principles and Research Packaging
- Wilkinson, M.D., et al. (2016). "The FAIR Guiding Principles for Scientific Data Management and Stewardship." *Scientific Data* 3:160018. [DOI: 10.1038/sdata.2016.18](https://doi.org/10.1038/sdata.2016.18)
- Soiland-Reyes, S., et al. (2022). "Packaging Research Artefacts with RO-Crate." *Data Science* 5(2). [DOI: 10.3233/DS-210053](https://doi.org/10.3233/DS-210053)

### RDF Versioning
- Taelman, R., Vander Sande, M., Van Herwegen, J., Mannens, E., Verborgh, R. (2018). "Triple Storage for Random-Access Versioned Querying of RDF Archives." *Journal of Web Semantics* 54:4–28. [DOI: 10.1016/j.websem.2018.08.001](https://doi.org/10.1016/j.websem.2018.08.001)

### OCI for ML/Data
- KitOps (CNCF Sandbox, 2025). [https://kitops.org/](https://kitops.org/)
- OMLMD — OCI-based ML Model Distribution (Red Hat, 2024). [https://github.com/containers/omlmd](https://github.com/containers/omlmd)

### OCI, ORAS, and Supply Chain Security
- OCI Distribution Specification v1.1. [https://github.com/opencontainers/distribution-spec](https://github.com/opencontainers/distribution-spec)
- OCI Image Manifest Specification (subject field, artifactType). [https://github.com/opencontainers/image-spec/blob/main/manifest.md](https://github.com/opencontainers/image-spec/blob/main/manifest.md)
- ORAS Project. [https://oras.land/](https://oras.land/)
- ORAS Attached Artifacts (referrers model). [https://oras.land/docs/concepts/reftypes/](https://oras.land/docs/concepts/reftypes/)
- Sigstore / Cosign. [https://docs.sigstore.dev/](https://docs.sigstore.dev/)
- SLSA (Supply-chain Levels for Software Artifacts) v1.0. [https://slsa.dev/spec/v1.0/](https://slsa.dev/spec/v1.0/)
- In-toto Attestation Framework v1. [https://github.com/in-toto/attestation](https://github.com/in-toto/attestation)
- SPDX (Software Package Data Exchange). [https://spdx.dev/](https://spdx.dev/)

### Provenance
- PROV-O: The PROV Ontology. W3C Recommendation, 2013. [https://www.w3.org/TR/prov-o/](https://www.w3.org/TR/prov-o/)
