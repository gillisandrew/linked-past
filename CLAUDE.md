# CLAUDE.md

## Build / Test

`uv run pytest` — no other test runner or build step.

## Architecture

- All CLI commands live flat in `dprr_tool/cli.py`. Do not create a `commands/` subdirectory.
- MCP server tools live in `dprr_tool/mcp_server.py`.
- YAML files in `dprr_tool/context/` are the ontology source of truth: `schemas.yaml` defines classes and predicates, `examples.yaml` has curated SPARQL pairs, `tips.yaml` has query pitfalls. Validation in `validate.py` reads these dynamically — to change the ontology, edit the YAML files, not Python code.
- One-off data scripts live in `scripts/` (e.g. `convert_n3_to_ttl.py`, `extract_from_endpoint.py`, `rebind_prefixes.py`). They are not part of the package.

## Store

- After first load, the Oxigraph store opens **read-only** (`Store.read_only()`) to avoid file locking. Do not add write operations to the initialized store.
- MCP server auto-initializes from `DPRR_RDF_FILE` env var if the store is empty.
- Tests create ephemeral stores using `SAMPLE_TURTLE` from `tests/test_store.py`.
