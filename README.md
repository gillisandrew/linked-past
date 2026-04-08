# linked-past

A monorepo for making ancient world linked data accessible to AI agents.

Scholars can ask natural language questions and receive well-cited results across multiple prosopographical, numismatic, epigraphic, and geographic datasets — with cross-references discovered automatically.

## Packages

| Package | Description |
|---------|-------------|
| [`linked-past`](packages/linked-past/) | MCP server providing 15 tools across 8 ancient world datasets (DPRR, Pleiades, PeriodO, Nomisma, CRRO, EDH, OCRE, RPC) with cross-dataset linkage, hybrid search, disambiguation, and scholarly citations |
| [`linked-past-viewer`](packages/linked-past-viewer/) | React web UI for exploring query results — markdown rendering, Mermaid diagrams, entity cards with live popover links, served at `/viewer` |
| [`linked-past-store`](packages/linked-past-store/) | Standalone library for distributing scholarly RDF datasets as OCI artifacts via container registries — content-addressable, version-tracked, annotated storage |

## Quickstart

### Docker (recommended)

```bash
# Pull and run (auto-downloads all datasets on first start)
docker run -d \
  -v linked-past-data:/data \
  -p 8000:8000 \
  -e LINKED_PAST_DATASETS=all \
  ghcr.io/gillisandrew/linked-past:main

# Connect with Claude Code
claude
```

Set `LINKED_PAST_DATASETS` to a comma-separated list (e.g., `dprr,pleiades,nomisma`) or `all`. Datasets are downloaded on first startup and cached in the `/data` volume. Subsequent starts skip the download. The viewer is available at `http://localhost:8000/viewer`.

### From source

```bash
# Install
uv sync

# Start the MCP server
uv run linked-past-server

# In another terminal, connect with Claude Code
claude
```

### CLI Commands

```bash
linked-past-server serve                         # Start MCP server (default)
linked-past-server status                        # Show installed datasets + OCI digests
linked-past-server update [datasets...] --all    # Download or update datasets from OCI
linked-past-server update --all --force          # Force re-pull even if cached
linked-past-server reload [datasets...]          # Re-open stores from disk (no download)
linked-past-server reindex                       # Rebuild search + meta-entity caches
```

## Development

This is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) monorepo. All packages share a single lockfile and virtual environment.

```bash
uv sync              # Install all packages + dev deps
uv run pytest        # Run all tests across packages
uv run ruff check .  # Lint all packages
```

### Working on a specific package

```bash
uv run --package linked-past pytest              # Tests for the MCP server
uv run --package linked-past-store pytest        # Tests for the store library
```

## Repository Structure

```
packages/
├── linked-past/              # MCP server + dataset plugins
│   ├── linked_past/
│   │   ├── core/             # Server, registry, store, validation, linkage, embeddings
│   │   ├── datasets/         # Plugin per dataset (dprr, pleiades, periodo, nomisma, crro, edh, ocre, rpc)
│   │   └── linkages/         # Curated cross-references + Wikidata concordances
│   └── tests/
├── linked-past-viewer/       # React web UI (Vite + React 19 + Tailwind)
│   ├── src/
│   └── ...
├── linked-past-store/        # OCI distribution library
│   ├── linked_past_store/    # Push, pull, sanitize, verify
│   └── tests/
scripts/                      # Dataset packaging scripts (download → sanitize → push to OCI)
docs/                         # Design specs and implementation plans
.github/workflows/            # CI + dispatchable dataset update workflow
```

## License

Software: [AGPL-3.0](LICENSE) (main package), [LGPL-3.0](packages/linked-past-store/LICENSE) (store library). Dataset licenses vary — see each dataset's OCI manifest annotations or the [linked-past package README](packages/linked-past/README.md#datasets).
