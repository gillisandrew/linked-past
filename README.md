# linked-past

A monorepo for making ancient world linked data accessible to AI agents.

Scholars can ask natural language questions and receive well-cited results across multiple prosopographical, numismatic, epigraphic, and geographic datasets — with cross-references discovered automatically.

## Packages

| Package | Description |
|---------|-------------|
| [`linked-past`](packages/linked-past/) | MCP server providing 10 SPARQL tools across 7 ancient world datasets (DPRR, Pleiades, PeriodO, Nomisma, CRRO, EDH, OCRE) with cross-dataset linkage, embedding-assisted discovery, and scholarly citations |
| [`linked-past-store`](packages/linked-past-store/) | Standalone library for distributing scholarly RDF datasets as OCI artifacts via container registries — content-addressable, version-tracked, annotated storage |

## Quickstart

### Docker (recommended)

```bash
# Pull and run
docker run -d \
  -v linked-past-data:/data \
  -p 8000:8000 \
  ghcr.io/gillisandrew/dprr-tool:main

# Initialize datasets (first run only)
docker exec -it <container> linked-past-server init --all

# Connect with Claude Code
claude
```

The `/data` volume persists datasets, Oxigraph stores, search indexes, and meta-entity caches across container restarts. Without a volume, data is lost when the container is removed.

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
linked-past-server serve                    # Start MCP server (default)
linked-past-server init [datasets...] --all # Download and initialize datasets
linked-past-server status                   # Show installed datasets
linked-past-server update [datasets...] --force  # Re-pull from OCI + reload
linked-past-server reload [datasets...]     # Re-open stores from disk
linked-past-server reindex                  # Rebuild search + meta-entity caches
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
│   │   ├── datasets/         # Plugin per dataset (dprr, pleiades, periodo, nomisma, crro, edh, ocre)
│   │   └── linkages/         # Curated cross-references + Wikidata concordances
│   └── tests/
├── linked-past-store/        # OCI distribution library
│   ├── linked_past_store/    # Push, pull, sanitize, verify
│   └── tests/
scripts/                      # Dataset packaging scripts (download → sanitize → push to OCI)
docs/                         # Design specs and implementation plans
.github/workflows/            # CI + dispatchable dataset update workflow
```

## License

Software: [AGPL-3.0](LICENSE) (main package), [LGPL-3.0](packages/linked-past-store/LICENSE) (store library). Dataset licenses vary — see each dataset's OCI manifest annotations or the [linked-past package README](packages/linked-past/README.md#datasets).
