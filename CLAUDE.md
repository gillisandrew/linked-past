# CLAUDE.md

## Build / Test / Lint

- `uv run pytest` — sole test runner, no build step.
- `uv run ruff check .` — lint. CI runs both.

## Architecture

- `dprr-server` is the sole entry point (MCP server). There is no CLI.
- YAML files in `dprr_tool/context/` are the ontology source of truth: `schemas.yaml` (classes/predicates), `examples.yaml` (SPARQL pairs), `tips.yaml` (pitfalls), `prefixes.yaml` (namespace map). Validation in `validate.py` reads these dynamically — to change the ontology, edit the YAML files, not Python code.
- One-off data scripts live in `scripts/`, not in the package.

## Store

- Data directory follows XDG: `DPRR_DATA_DIR` > `$XDG_DATA_HOME/dprr-tool` > `~/.local/share/dprr-tool`.
- On first startup, if no `dprr.ttl` exists in the data directory, the server auto-downloads it from the latest GitHub release. Override the URL with `DPRR_DATA_URL`.
- After first load, the Oxigraph store opens **read-only** (`Store.read_only()`) to avoid file locking. Do not add write operations to the initialized store.
- Tests create ephemeral stores using `SAMPLE_TURTLE` from `tests/test_store.py`. Do not mock the store.
