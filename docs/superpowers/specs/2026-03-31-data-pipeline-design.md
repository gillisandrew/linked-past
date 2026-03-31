# Data Pipeline Redesign

Split the monolithic package scripts into a three-stage pipeline: ingest raw data, clean and publish, then validate. A central `datasets.yaml` config is the single source of truth for all dataset metadata, OCI refs, and pipeline policy.

## Pipeline Architecture

```
Stage 1: INGEST (manual, per-dataset scripts)
  Upstream source → download → convert to Turtle → push raw OCI artifact
  ghcr.io/gillisandrew/linked-past/raw/{dataset}:latest

Stage 2: CLEAN (CI workflow_dispatch, generic script)
  Pull raw OCI artifact → sanitize → verify → VoID → schema → push clean artifact
  ghcr.io/gillisandrew/linked-past/datasets/{dataset}:latest

Stage 3: VALIDATE (runs automatically after clean in CI)
  Pull clean artifact → triple count regression check → schema diff
  Fails the CI job if thresholds are breached
```

### Separation of Concerns

- **Ingest** is messy — each upstream source has its own format, download method, and quirks. Per-dataset scripts handle this.
- **Clean** is uniform — once data is raw Turtle in OCI, sanitization, verification, metadata generation, and publication are the same for every dataset. One generic script.
- **Validate** is uniform — triple count and schema checks are dataset-agnostic. One generic script.

### Provenance Chain

Clean artifacts carry an `io.github.gillisandrew.linked-past.raw-digest` annotation linking back to the exact raw artifact they were built from. This provides a full provenance chain: clean artifact → raw artifact (by digest) → upstream source (by annotation).

## `datasets.yaml`

Central configuration at the repository root. Single source of truth for OCI refs, annotations, ingest scripts, and validation thresholds.

### Schema

```yaml
{dataset_name}:
  # OCI references
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/{dataset}:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/{dataset}:latest

  # Ingest configuration
  ingest_script: scripts/ingest_{dataset}.py   # or scripts/ingest_generic.py
  fetch_url: https://...                        # only for ingest_generic.py
  source_format: rdf-xml | turtle | json-ld     # only for ingest_generic.py

  # Validation
  min_triple_count: 600000

  # OCI annotations (carried through from ingest → clean)
  license: CC-BY-NC-4.0
  source_url: https://...
  description: "Human-readable dataset description"
  citation: |
    @misc{citation_key,
      author = {...},
      title  = {...},
      ...
    }
```

### Field Usage by Stage

| Field | Ingest | Clean | Validate |
|-------|--------|-------|----------|
| `raw_ref` | push target | pull source | — |
| `clean_ref` | — | push target | pull source |
| `ingest_script` | determines which script runs | — | — |
| `fetch_url` | generic ingest only | — | — |
| `source_format` | generic ingest only | — | — |
| `min_triple_count` | — | — | threshold check |
| `license` | annotation | annotation | — |
| `source_url` | annotation | annotation | — |
| `description` | annotation | annotation | — |
| `citation` | annotation (rendered to plain text) | annotation (rendered to plain text) | — |

### Full Example

```yaml
dprr:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/dprr:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/dprr:latest
  ingest_script: scripts/ingest_dprr.py
  min_triple_count: 600000
  license: CC-BY-NC-4.0
  source_url: https://romanrepublic.ac.uk
  description: "Digital Prosopography of the Roman Republic — persons, offices, relationships (509-31 BC)"
  citation: |
    @misc{mouritsen2017dprr,
      author       = {Mouritsen, Henrik and Rathbone, Dominic and Bradley, John and Robb, Maggie},
      title        = {{Digital Prosopography of the Roman Republic}},
      year         = {2017},
      howpublished = {\url{https://romanrepublic.ac.uk/}},
      publisher    = {King's College London},
      note         = {AHRC-funded project. Maintained by King's Digital Lab. CC BY-NC 4.0}
    }

pleiades:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/pleiades:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/pleiades:latest
  ingest_script: scripts/ingest_pleiades.py
  min_triple_count: 2500000
  license: CC-BY-3.0
  source_url: https://pleiades.stoa.org/
  description: "Gazetteer of ancient places — coordinates, names, time periods"
  citation: |
    @misc{pleiades,
      author       = {Bagnall, Roger and Talbert, Richard and Elliott, Tom and Gillies, Sean},
      title        = {Pleiades: A Gazetteer of Past Places},
      howpublished = {\url{https://pleiades.stoa.org/}},
      year         = {2006--2025},
      doi          = {10.5281/zenodo.1193921},
      note         = {CC BY 3.0}
    }

periodo:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/periodo:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/periodo:latest
  ingest_script: scripts/ingest_periodo.py
  min_triple_count: 170000
  license: CC0-1.0
  source_url: https://perio.do/
  description: "Gazetteer of period definitions from scholarly sources"
  citation: |
    @misc{periodo,
      author       = {Rabinowitz, Adam and Shaw, Ryan},
      title        = {{PeriodO}: A Gazetteer of Period Definitions},
      howpublished = {\url{https://perio.do/}},
      year         = {2014--2026},
      note         = {Canonical dataset: \url{http://n2t.net/ark:/99152/p0d}. CC0 1.0}
    }

nomisma:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/nomisma:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/nomisma:latest
  ingest_script: scripts/ingest_nomisma.py
  min_triple_count: 400000
  license: CC-BY-4.0
  source_url: http://nomisma.org/
  description: "Numismatic concept vocabulary — persons, mints, denominations"
  citation: |
    @misc{nomisma_org,
      author       = {Gruber, Ethan and Meadows, Andrew and Heath, Sebastian},
      title        = {{Nomisma.org: Linked Open Data for Numismatics}},
      howpublished = {\url{http://nomisma.org/}},
      year         = {2010},
      note         = {American Numismatic Society, ISAW (NYU), DAI. CC BY 4.0}
    }

crro:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/crro:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/crro:latest
  ingest_script: scripts/ingest_generic.py
  fetch_url: https://numismatics.org/crro/nomisma.rdf
  source_format: rdf-xml
  min_triple_count: 50000
  license: ODbL-1.0
  source_url: https://numismatics.org/crro/
  description: "Roman Republican coin types (Crawford's RRC) — 2,602 types with iconography and Nomisma links"
  citation: |
    @misc{gruber_crro,
      author       = {Gruber, Ethan},
      title        = {{Coinage of the Roman Republic Online (CRRO)}},
      year         = {2015},
      howpublished = {\url{https://numismatics.org/crro/}},
      note         = {American Numismatic Society. Based on Crawford, M.H. (1974) Roman Republican Coinage. ODbL 1.0}
    }

ocre:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/ocre:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/ocre:latest
  ingest_script: scripts/ingest_generic.py
  fetch_url: https://numismatics.org/ocre/nomisma.rdf
  source_format: rdf-xml
  min_triple_count: 1100000
  license: ODbL-1.0
  source_url: https://numismatics.org/ocre/
  description: "Roman Imperial coin types (RIC) — ~50,000 types with iconography and Nomisma links"
  citation: |
    @misc{gruber_ocre,
      author       = {Gruber, Ethan},
      title        = {{Online Coins of the Roman Empire (OCRE)}},
      year         = {2012},
      howpublished = {\url{https://numismatics.org/ocre/}},
      note         = {American Numismatic Society and ISAW (NYU). ODbL 1.0}
    }

edh:
  raw_ref: ghcr.io/gillisandrew/linked-past/raw/edh:latest
  clean_ref: ghcr.io/gillisandrew/linked-past/datasets/edh:latest
  ingest_script: scripts/ingest_edh.py
  min_triple_count: 1500000
  license: CC-BY-SA-4.0
  source_url: https://edh.ub.uni-heidelberg.de/
  description: "81,000+ Latin inscriptions with transcriptions, findspots, and dates"
  citation: |
    @misc{edh,
      author       = {{Epigraphic Database Heidelberg}},
      title        = {Epigraphic Database Heidelberg},
      howpublished = {\url{https://edh.ub.uni-heidelberg.de/}},
      year         = {1997--2021},
      note         = {Founded by G\'eza Alf\"oldy; directed by Christian Witschel. Heidelberg Academy of Sciences and Humanities. CC BY-SA 4.0}
    }
```

## Scripts

### Ingest Scripts

Located in `scripts/`. Each takes no arguments — reads its config from `datasets.yaml`.

**Custom ingest scripts** (datasets with upstream quirks):
- `ingest_dprr.py` — downloads tar.gz from GitHub release (`https://github.com/gillisandrew/dprr-mcp/releases/latest/download/dprr-data.tar.gz`), extracts Turtle, pushes to `raw_ref`
- `ingest_pleiades.py` — downloads tar.gz from atlantides.org, concatenates multiple .ttl files, pushes to `raw_ref`
- `ingest_periodo.py` — downloads JSON-LD from `http://n2t.net/ark:/99152/p0d.jsonld`, converts to Turtle via rdflib, pushes to `raw_ref`
- `ingest_nomisma.py` — downloads RDF/XML from nomisma.org, converts to Turtle via rapper, removes bad Unicode lines, pushes to `raw_ref`
- `ingest_edh.py` — reads local `edh_linked_data.zip`, extracts Turtle files, pushes to `raw_ref`

**Generic ingest script** (`ingest_generic.py`):
- Reads `fetch_url` and `source_format` from `datasets.yaml`
- Downloads the URL
- Converts to Turtle if `source_format` is `rdf-xml` (via rapper) or `json-ld` (via rdflib)
- Pushes to `raw_ref`
- Used by CRRO and OCRE (straightforward RDF/XML downloads with no special handling)

**All ingest scripts**:
1. Read their dataset entry from `datasets.yaml`
2. Download/extract upstream data
3. Convert to Turtle if needed (no sanitization — that's the clean step)
4. Push to `raw_ref` with OCI annotations from config (`license`, `source_url`, `description`, citation rendered to plain text)

### Clean Script

`scripts/clean_dataset.py <dataset>`

Generic for all datasets. Steps:

1. Load `datasets.yaml`, look up the dataset entry
2. Pull from `raw_ref` via linked-past-store. Record the raw artifact digest.
3. Sanitize the Turtle (`sanitize_turtle()` — BCP 47 fixes, bare DOI scheme fixes, bad Unicode)
4. Verify via Oxigraph (`verify_turtle()` — confirms triples load cleanly, returns triple count)
5. Generate VoID description (`generate_void()`)
6. Extract schema (`extract_schema()` — ontology-aware if ontology available + empirical from data)
7. Push to `clean_ref` with:
   - All annotations from `datasets.yaml` (license, source_url, description, citation)
   - `io.github.gillisandrew.linked-past.raw-digest` set to the raw artifact's digest
   - `io.github.gillisandrew.linked-past.triples` set to the verified triple count

### Validate Script

`scripts/validate_dataset.py <dataset>`

Post-push validation. Steps:

1. Load `datasets.yaml`, look up `clean_ref` and `min_triple_count`
2. Pull the clean artifact from `clean_ref`
3. Load into Oxigraph, count triples
4. **Triple count check**: fail (exit 1) if count < `min_triple_count`

Also exports `diff_schemas()` which is imported by `clean_dataset.py`.

**Schema diff** runs during the clean step (not validate) because both the old and new schemas are in memory before the push. By the time validate runs, the OCI cache contains the newly-pushed artifact, making it impossible to retrieve the previous schema. The clean script pulls the previous clean artifact, loads its `_schema.yaml`, then compares against the freshly extracted schema before pushing.

Output example:
```
=== Cleaning dprr ===
...
dprr schema diff:
  + Added class: TribalAssertion (4 properties)
  ~ Changed class Person: +1 property (hasWikidataID)
  No removed classes.
Pushed clean: ghcr.io/gillisandrew/linked-past/datasets/dprr:latest

=== Validating dprr ===
PASS: dprr — 654,125 triples (min: 600,000)
```

## CI Workflows

### `clean-datasets.yml` (replaces `update-datasets.yml`)

Triggered manually via workflow_dispatch.

```yaml
on:
  workflow_dispatch:
    inputs:
      dataset:
        description: Dataset to clean and publish
        required: true
        type: choice
        options: [dprr, pleiades, periodo, nomisma, crro, ocre, edh, all]
      version:
        description: Version tag
        required: false
        default: latest
        type: string
```

Steps:
1. Checkout repository
2. Install uv, Python 3.13, oras CLI
3. Login to GHCR (`docker/login-action`)
4. For each selected dataset:
   - `uv run python scripts/clean_dataset.py {dataset}`
   - `uv run python scripts/validate_dataset.py {dataset}`
5. If `version` ≠ `latest`, tag the clean artifact with the version

CI fails if any validation step exits non-zero (triple count below threshold).

### `ci.yml` (unchanged)

Lint and tests on push/PR to main. No dataset operations.

## What Gets Retired

The existing `scripts/package_*.py` scripts are replaced by the ingest + clean split. They can be deleted once the new pipeline is confirmed working.

The existing `.github/workflows/update-datasets.yml` is replaced by `clean-datasets.yml`.

## OCI Annotation Summary

Annotations set on both raw and clean artifacts:

| Annotation | Source | Example |
|---|---|---|
| `org.opencontainers.image.licenses` | `datasets.yaml` → `license` | `CC-BY-NC-4.0` |
| `org.opencontainers.image.source` | `datasets.yaml` → `source_url` | `https://romanrepublic.ac.uk` |
| `org.opencontainers.image.description` | `datasets.yaml` → `description` | `Digital Prosopography...` |
| `org.opencontainers.image.url` | hardcoded | `https://github.com/gillisandrew/linked-past` |
| `io.github.gillisandrew.linked-past.citation` | `datasets.yaml` → `citation` (rendered) | `Mouritsen et al. (2017)...` |
| `io.github.gillisandrew.linked-past.dataset` | dataset key from `datasets.yaml` | `dprr` |
| `io.github.gillisandrew.linked-past.format` | hardcoded | `text/turtle` |
| `io.github.gillisandrew.linked-past.source-url` | fetch URL used by ingest | `https://atlantides.org/...` |

Additional annotations on clean artifacts only:

| Annotation | Source | Example |
|---|---|---|
| `io.github.gillisandrew.linked-past.raw-digest` | recorded during pull | `sha256:2aee...` |
| `io.github.gillisandrew.linked-past.triples` | from Oxigraph verify | `654125` |
| `org.opencontainers.image.version` | CI `version` input | `latest` |
