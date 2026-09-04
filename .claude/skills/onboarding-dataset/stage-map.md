# Stage Map: every file touched when onboarding a dataset

Copy the closest existing example rather than starting from a blank file.

## Stage 1: Ingest

| File | Purpose | Closest example |
|------|---------|-----------------|
| `datasets.yaml` | Single source of truth: refs, license, citation, threshold, fetch settings | `crro` (generic RDF/XML), `pleiades` (bespoke) |
| `scripts/ingest_generic.py` | Handles `fetch_url` + `source_format` in {`rdf-xml`, `json-ld`, `turtle`} | used by crro, ocre, rpc |
| `scripts/ingest_<name>.py` | Bespoke download/convert/push | `ingest_dprr.py` (tarball), `ingest_periodo.py` (JSON-LD), `ingest_nomisma.py` (RDF/XML with URI repair), `ingest_edh.py` (local zip), `ingest_pleiades.py` (multi-file Turtle) |
| `scripts/extract_from_endpoint.py` | Dump a SPARQL endpoint to Turtle | DPRR endpoint behind a bot shield |
| `scripts/convert_n3_to_ttl.py`, `scripts/rebind_prefixes.py` | N3 to Turtle; namespace rebinding | DPRR |
| `.github/workflows/ingest-<name>.yml` | Scheduled ingest | `ingest-pleiades.yml` |
| `scripts/pipeline_config.py` | `load_dataset_config`, `build_annotations` (do not edit; import) | |

## Stage 2: Clean

| File | Purpose | Closest example |
|------|---------|-----------------|
| `scripts/clean_dataset.py` | Pull raw, sanitize, verify, VoID, schema, ontology sidecar, diff, push clean | generic; driven by `datasets.yaml` |
| `scripts/validate_dataset.py` | Pull clean, verify, enforce `min_triple_count` | generic |
| `packages/linked-past-store/linked_past_store/sanitize.py` | Generic Turtle fixes (`_regex_fixes`) | BCP 47 tags, bare DOIs |
| `scripts/fix_pleiades_refs.py` | Example of a dataset-specific repair applied at ingest | Pleiades |
| `docs/data-lifecycle.md` | Catalog of upstream data issues; add a row for any new class | |
| `.github/workflows/clean-datasets.yml` | Add the dataset to the `options` list | |

## Stage 3: Context

| File | Purpose | Closest example |
|------|---------|-----------------|
| `packages/linked-past/linked_past/datasets/<name>/__init__.py` | Empty package marker | any |
| `packages/linked-past/linked_past/datasets/<name>/plugin.py` | `DatasetPlugin` subclass with metadata attributes | `edh/plugin.py` (minimal), `crro/plugin.py` (with `get_version_info` and `extra_search_entries`) |
| `packages/linked-past/linked_past/datasets/<name>/context/prefixes.yaml` | Prefix map | `edh/context/prefixes.yaml` |
| `.../context/schemas.yaml` | Hand-written classes and properties | `edh/context/schemas.yaml` |
| `.../context/examples.yaml` | Question + SPARQL pairs | `edh/context/examples.yaml` |
| `.../context/tips.yaml` | Query quirks tagged by class | `edh/context/tips.yaml` |
| `packages/linked-past/linked_past/datasets/__init__.py` | Import + `__all__` entry | |
| `packages/linked-past/linked_past/core/registry.py` | `_URI_NAMESPACES` entry | |
| `packages/linked-past/tests/conftest.py` | `ALL_DATASETS` + plugin map | |
| `packages/linked-past/tests/test_plugins.py` | `PLUGIN_SPECS` entry | |

## Stage 4: Index

| File | Purpose | Closest example |
|------|---------|-----------------|
| `.../datasets/<name>/plugin.py` `extra_search_entries` | Enriched search rows | `crro/plugin.py` via `datasets/coin_types.py` |
| `packages/linked-past/linked_past/core/server.py` `_index_dataset` | Automatic label indexing (read, do not edit) | |

## Stage 5: Link

| File | Purpose | Closest example |
|------|---------|-----------------|
| `packages/linked-past/linked_past/linkages/<source>_<target>.yaml` (append `_<confidence>` only when one pair is split across confidence levels) | Curated links; every `*.yaml` in the directory is loaded, `metadata.confidence` is the file default | `dprr_pleiades.yaml`; `dprr_nomisma_confirmed.yaml` with `dprr_nomisma_probable.yaml` |
| Pleiades targets in any linkage file | Use the bare record URI `https://pleiades.stoa.org/places/<id>`, as upstream publishes; `#this` is accepted and normalised by `canonical_uri` in `core/linkage.py` | `kerameikos_pleiades.yaml` |
| `packages/linked-past/linked_past/linkages/wikidata/*.ttl` | Wikidata concordances | |

## Docs

| File | Purpose |
|------|---------|
| `README.md` | Dataset count and list |
| `docs/data-lifecycle.md` | Issue catalog |
