# linked-past

Multi-dataset prosopographical SPARQL tools for AI agents. Natural-language queries with scholarly citations across linked ancient world datasets.

## What It Does

An MCP server that gives AI agents structured access to ancient world linked data. A scholar can ask a natural language question and receive well-cited results with easy ways to explore across datasets.

### Datasets

| Dataset | Description | Triples | License |
|---------|-------------|---------|---------|
| [DPRR](https://romanrepublic.ac.uk/) | Digital Prosopography of the Roman Republic — persons, offices, relationships | 654K | CC BY-NC 4.0 |
| [Pleiades](https://pleiades.stoa.org/) | Gazetteer of ancient places — coordinates, names, time periods | 2.96M | CC BY 3.0 |
| [PeriodO](https://perio.do/) | Gazetteer of period definitions from scholarly sources | 188K | CC0 |
| [Nomisma](https://nomisma.org/) | Numismatic concept vocabulary — persons, mints, denominations | 466K | CC BY 4.0 |
| [CRRO](https://numismatics.org/crro/) | Roman Republican coin types (Crawford's RRC) | 54K | ODbL 1.0 |
| [OCRE](https://numismatics.org/ocre/) | Roman Imperial coin types (RIC) — ~50K types with iconography | 1.2M | ODbL 1.0 |
| [EDH](https://edh.ub.uni-heidelberg.de/) | 81,000+ Latin inscriptions with transcriptions and findspots | 1.6M | CC BY-SA 4.0 |

Datasets are distributed as OCI artifacts via `ghcr.io/gillisandrew/linked-past/`. Each dataset's license is declared in the OCI manifest annotations. See [LICENSE](#license) for details.

### MCP Tools

| Tool | Description |
|------|-------------|
| `discover_datasets` | Find available datasets by topic (semantic search via embeddings) |
| `get_schema` | Get ontology overview — prefixes, classes, query tips |
| `validate_sparql` | Check syntax, auto-repair prefixes, validate against schema |
| `query` | Execute SPARQL with citation footer and "See also" cross-references |
| `search_entities` | Find entities by name across all datasets |
| `explore_entity` | Inspect entity properties + cross-dataset links |
| `find_links` | Discover cross-references (curated linkage graph + in-data SKOS/OWL) |
| `get_provenance` | Scholarly citation drill-down |
| `update_dataset` | Check freshness or initialize unloaded datasets from OCI |

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run linked-past-server
```

On first startup, datasets are pulled from OCI as needed. Use `update_dataset` via the MCP tools to trigger initialization of specific datasets.

Data is stored in `$XDG_DATA_HOME/linked-past/` (defaults to `~/.local/share/linked-past/`). Override with `LINKED_PAST_DATA_DIR`.

### Docker

```bash
docker build -t linked-past .
docker run -p 8000:8000 -v linked-past-data:/root/.local/share/linked-past linked-past
```

### MCP Client Configuration

Start the server, then configure your MCP client:

```json
{
  "mcpServers": {
    "linked-past": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

## Architecture

```
MCP Tools (10)
  discover_datasets, get_schema, validate_sparql, query,
  search_entities, explore_entity, find_links,
  get_provenance, update_dataset
        │
Embedding Retrieval (fastembed + SQLite)
  Indexes examples, tips, schemas across all datasets
        │
Linkage Graph (in-memory Oxigraph)
  193 curated DPRR↔Nomisma person links
  ~9K Wikidata-derived concordances (Pleiades↔TM, Nomisma↔Pleiades)
  + runtime discovery of SKOS/OWL xrefs in dataset stores
        │
Dataset Plugins (7)
  Each: plugin.py + context/ (schemas, examples, tips, prefixes YAML)
  Fetched via ORAS from ghcr.io/gillisandrew/linked-past/{dataset}
        │
Oxigraph Stores (read-only, per-dataset)
  ~6M triples across 7 datasets
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `LINKED_PAST_DATA_DIR` | Override data directory |
| `LINKED_PAST_QUERY_TIMEOUT` | Query timeout in seconds (default: 600) |
| `LINKED_PAST_REGISTRY` | Override OCI registry (default: `ghcr.io/gillisandrew/linked-past`) |

## Development

```bash
uv run pytest        # 139 tests
uv run ruff check .  # lint
```

### Adding a Dataset

1. Create `linked_past/datasets/{name}/` with `plugin.py` and `context/` YAML files
2. Follow the `DatasetPlugin` ABC in `linked_past/datasets/base.py`
3. Register in `linked_past/core/server.py`
4. Add the dataset entry to `datasets.yaml` (OCI refs, license, citation, thresholds)
5. Create an ingest script (`scripts/ingest_{name}.py`) or use `scripts/ingest_generic.py` with `fetch_url`/`source_format`
6. Add URI namespace to `linked_past/core/registry.py`

### Data Pipeline

Raw data ingestion (run manually, pushes to `raw/` OCI namespace):
```bash
uv run python scripts/ingest_pleiades.py
uv run python scripts/ingest_generic.py crro
# etc.
```

Cleaning and publishing (run via CI or locally, pulls from raw, pushes to `datasets/`):
```bash
uv run python scripts/clean_dataset.py pleiades
uv run python scripts/validate_dataset.py pleiades
```

All dataset metadata (OCI refs, licenses, citations, thresholds) lives in `datasets.yaml` at the repo root.

## License

This software is released under the [GNU Affero General Public License v3.0](../../LICENSE) (AGPL-3.0).

**Dataset licenses vary.** Each dataset is distributed as a separate OCI artifact with its license declared in the manifest annotations (`org.opencontainers.image.licenses`). Check the individual dataset's OCI manifest or the table above for the applicable license. The software does not bundle any dataset data — it pulls datasets from OCI at runtime.

## Citing

```bibtex
@software{linked_past,
  author    = {Gillis, Andrew},
  title     = {linked-past: Multi-Dataset Prosopographical {SPARQL} Tools for {AI} Agents},
  year      = {2026},
  url       = {https://github.com/gillisandrew/linked-past}
}
```
