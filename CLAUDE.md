# CLAUDE.md

## Build / Test / Lint

- `uv run pytest` — sole test runner, no build step. Runs tests across all workspace packages.
- `uv run ruff check .` — lint. CI runs both.

## Monorepo Structure

This is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) monorepo with two packages:

- `packages/linked-past/` — MCP server + dataset plugins
- `packages/linked-past-store/` — Standalone OCI distribution library for scholarly RDF datasets

Root `pyproject.toml` is workspace config only. Each package has its own `pyproject.toml`.
`datasets.yaml` at the root is the single source of truth for all dataset metadata (OCI refs, licenses, citations, validation thresholds).

## Architecture (linked-past package)

- `linked-past-server` is the sole entry point (MCP server over streamable-http).
- Plugin-based: each dataset lives in `packages/linked-past/linked_past/datasets/{name}/` with a `plugin.py` (implements `DatasetPlugin` ABC) and `context/` directory (YAML files: schemas, examples, tips, prefixes).
- Core modules in `packages/linked-past/linked_past/core/`: server, registry, store, validate, linkage, embeddings, fetch.
- YAML files in each dataset's `context/` are the ontology source of truth. To change a dataset's schema, edit the YAML files, not Python code.
- Ingest scripts (`scripts/ingest_*.py`) push raw data to OCI. `scripts/clean_dataset.py` and `scripts/validate_dataset.py` are generic pipeline stages. One-off analysis scripts also live in `scripts/`.

## Store

- Data directory follows XDG: `LINKED_PAST_DATA_DIR` > `$XDG_DATA_HOME/linked-past` > `~/.local/share/linked-past`.
- Each dataset gets its own Oxigraph store at `{data_dir}/{dataset}/store/`.
- Datasets are fetched via ORAS (using `linked-past-store` package) from `ghcr.io/gillisandrew/linked-past/{dataset}`.
- Server uses lazy startup (`initialize_cached`): only opens stores already on disk. Use `update_dataset` tool to pull new datasets.
- After load, stores open **read-only** (`Store.read_only()`) to avoid file locking. Do not add write operations to initialized stores.
- The linkage graph uses an **in-memory** Oxigraph store (rebuilt from YAML + Turtle files on each startup).

## Validation

- Tier 1: SPARQL syntax + auto-repair missing PREFIX declarations (core, dataset-agnostic).
- Tier 2: Semantic validation against dataset schema dict (dataset-specific plugin method).
- Unknown classes and predicates are **warnings** (logged), not errors. Multi-vocabulary datasets use shared ontologies (LAWD, FOAF, SKOS, Dublin Core, ORG) whose terms aren't in the dataset-specific schema YAML.

## Cross-Dataset Linking

- Curated links in `packages/linked-past/linked_past/linkages/*.yaml` (DPRR↔Nomisma, DPRR↔Pleiades, DPRR↔PeriodO).
- Wikidata-derived concordances in `packages/linked-past/linked_past/linkages/wikidata/*.ttl`.
- `find_links` and `explore_entity` also discover SKOS/OWL cross-references (`closeMatch`, `exactMatch`, `sameAs`) from dataset stores at query time.

## Testing

- Tests live in each package: `packages/linked-past/tests/`, `packages/linked-past-store/tests/`.
- Tests create ephemeral stores with inline SAMPLE_TURTLE fixtures. Do not mock the store.
- Integration tests use `build_app_context(eager=True)` and patch all plugin `fetch()` methods.
- When adding a new dataset plugin, add fetch patches to `tests/test_server.py`, `tests/test_linked_past_integration.py`, and `tests/test_multi_dataset_integration.py`.
