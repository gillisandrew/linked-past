# CLAUDE.md

## Build / Test / Lint

- `uv run pytest` — sole test runner, no build step.
- `uv run ruff check .` — lint. CI runs both.

## Architecture

- `linked-past-server` is the sole entry point (MCP server over streamable-http).
- Plugin-based: each dataset lives in `linked_past/datasets/{name}/` with a `plugin.py` (implements `DatasetPlugin` ABC) and `context/` directory (YAML files: schemas, examples, tips, prefixes).
- Core modules in `linked_past/core/`: server, registry, store, validate, linkage, embeddings, fetch.
- YAML files in each dataset's `context/` are the ontology source of truth. To change a dataset's schema, edit the YAML files, not Python code.
- One-off data scripts live in `scripts/`, not in the package.

## Store

- Data directory follows XDG: `LINKED_PAST_DATA_DIR` > `$XDG_DATA_HOME/linked-past` > `~/.local/share/linked-past`.
- Each dataset gets its own Oxigraph store at `{data_dir}/{dataset}/store/`.
- Datasets are fetched via ORAS from `ghcr.io/gillisandrew/linked-past/{dataset}`.
- Server uses lazy startup (`initialize_cached`): only opens stores already on disk. Use `update_dataset` tool to pull new datasets.
- After load, stores open **read-only** (`Store.read_only()`) to avoid file locking. Do not add write operations to initialized stores.
- The linkage graph uses an **in-memory** Oxigraph store (rebuilt from YAML + Turtle files on each startup).

## Validation

- Tier 1: SPARQL syntax + auto-repair missing PREFIX declarations (core, dataset-agnostic).
- Tier 2: Semantic validation against dataset schema dict (dataset-specific plugin method).
- Unknown classes and predicates are **warnings** (logged), not errors. Multi-vocabulary datasets use shared ontologies (LAWD, FOAF, SKOS, Dublin Core, ORG) whose terms aren't in the dataset-specific schema YAML.

## Cross-Dataset Linking

- Curated links in `linked_past/linkages/*.yaml` (DPRR↔Nomisma, DPRR↔Pleiades, DPRR↔PeriodO).
- Wikidata-derived concordances in `linked_past/linkages/wikidata/*.ttl`.
- `find_links` and `explore_entity` also discover SKOS/OWL cross-references (`closeMatch`, `exactMatch`, `sameAs`) from dataset stores at query time.

## Testing

- Tests create ephemeral stores with inline SAMPLE_TURTLE fixtures. Do not mock the store.
- Integration tests use `build_app_context(eager=True)` and patch all plugin `fetch()` methods.
- When adding a new dataset plugin, add fetch patches to `tests/test_server.py`, `tests/test_linked_past_integration.py`, and `tests/test_multi_dataset_integration.py`.
