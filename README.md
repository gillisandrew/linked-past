# dprr-mcp

Natural language SPARQL queries for the [Digital Prosopography of the Roman Republic](http://romanrepublic.ac.uk/) (DPRR). Ask questions about ~4,800 Roman individuals (509–31 BC) — their offices, family relationships, social statuses, and life dates — and get validated SPARQL queries and academic prose summaries.

## Before You Begin

**Strongly recommended reading:** [Caveat Utilitor](./CAVEAT_UTILITOR.md) — a detailed guide to the risks, biases, and inferential fallacies inherent in the DPRR dataset. The database documents a narrow, elite slice of Roman Republican society filtered through multiple layers of modern scholarly interpretation. Absence of evidence is not evidence of absence, naming conventions are ambiguous, and coverage varies dramatically by period. Read this document before drawing conclusions from query results.

## Setup

### From source

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run dprr-server
```

### Docker

Prebuilt images are published to GHCR on every release:

```bash
docker run -p 8000:8000 ghcr.io/gillisandrew/dprr-mcp:latest
```

Or build locally:

```bash
docker build -t dprr-mcp .
docker run -p 8000:8000 dprr-mcp
```

To persist the auto-downloaded data across container restarts, mount a volume:

```bash
docker run -p 8000:8000 -v dprr-data:/root/.local/share/dprr-mcp ghcr.io/gillisandrew/dprr-mcp:latest
```

### Data

On first startup, the server automatically downloads the DPRR RDF dataset from the latest GitHub release and initializes the local Oxigraph store. No manual data setup is required.

**Why bundle the data?** The upstream DPRR site ([romanrepublic.ac.uk](http://romanrepublic.ac.uk/)) experiences frequent downtime and serves a proof-of-work challenge page that blocks programmatic access. Bundling a snapshot of the RDF export in each release ensures the server can initialize reliably without depending on upstream availability. The dataset is distributed under its original [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) license.

Data is stored in `$XDG_DATA_HOME/dprr-mcp/` (defaults to `~/.local/share/dprr-mcp/`). Override with `DPRR_DATA_DIR`.

## Usage

### MCP Server

The server uses the `streamable-http` transport — it runs as a standalone HTTP process that MCP clients connect to over the network.

```bash
# From source:
uv run dprr-server

# Custom host/port:
uv run dprr-server --host 0.0.0.0 --port 9000

# Docker:
docker run -p 8000:8000 ghcr.io/gillisandrew/dprr-mcp:latest
```

The server listens on `http://127.0.0.1:8000/mcp` by default. A health check endpoint is available at `/healthz`. Queries that exceed the timeout (default 600s, configurable via `DPRR_QUERY_TIMEOUT`) return a structured error instead of crashing the connection.

#### MCP Tools

| Tool | Description |
|------|-------------|
| `get_schema` | Returns DPRR ontology prefixes, schema, 30 curated example query pairs, and query tips |
| `validate_sparql` | Syntax check, auto-repairs missing PREFIX declarations, semantic validation against the ontology |
| `execute_sparql` | Full validation + execution against the local Oxigraph RDF store |

#### Claude Code configuration

Start the server, then configure Claude Code to connect. Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "dprr": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

#### Claude Desktop configuration

Start the server, then add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dprr": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

### Claude Code Skill

With the MCP server configured, use the built-in skill:

```
/dprr Who held the office of praetor in 150 BC?
```

Claude will load the DPRR schema, generate a SPARQL query, validate and execute it, then synthesize the results into an academic summary with source citations and uncertainty flags.

## Architecture

```
┌─────────────────────────────────────┐
│  Claude Code Skill (/dprr)          │  System prompt with DPRR domain knowledge
│  Orchestrates: analyze → generate   │
│  → validate → execute → synthesize  │
└──────────────┬──────────────────────┘
               │ MCP protocol (streamable-http)
┌──────────────▼──────────────────────┐
│  MCP Server (dprr-server)           │  3 tools: get_schema, validate_sparql,
│  Python, streamable-http            │  execute_sparql
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Local Oxigraph Store               │  RDF triples from DPRR dataset
└─────────────────────────────────────┘
```

The MCP server + skill path lets Claude orchestrate the pipeline with no additional API calls needed.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DPRR_DATA_DIR` | Override data directory (default: `$XDG_DATA_HOME/dprr-mcp`) |
| `DPRR_DATA_URL` | Override URL for auto-downloading the data tarball |
| `DPRR_QUERY_TIMEOUT` | Query timeout in seconds (default: 600) |

## References

This tool queries data from the [Digital Prosopography of the Roman Republic](http://romanrepublic.ac.uk/) (DPRR), which draws on the following secondary sources:

```bibtex
@misc{dprr,
  author       = {Mouritsen, Henrik and Mayfield, Jamie and Bradley, John},
  title        = {Digital Prosopography of the Roman Republic ({DPRR})},
  year         = {2017},
  publisher    = {King's Digital Lab, King's College London},
  url          = {https://romanrepublic.ac.uk/},
  note         = {AHRC grant AH/K007211/1}
}

@book{broughton1951,
  author    = {Broughton, T. Robert S.},
  title     = {The Magistrates of the Roman Republic},
  volume    = {1: 509 B.C.--100 B.C.},
  series    = {Philological Monographs},
  number    = {15},
  publisher = {American Philological Association},
  address   = {New York},
  year      = {1951}
}

@book{broughton1952,
  author    = {Broughton, T. Robert S.},
  title     = {The Magistrates of the Roman Republic},
  volume    = {2: 99 B.C.--31 B.C.},
  series    = {Philological Monographs},
  number    = {15},
  publisher = {American Philological Association},
  address   = {New York},
  year      = {1952}
}

@book{broughton1986,
  author    = {Broughton, T. Robert S.},
  title     = {The Magistrates of the Roman Republic},
  volume    = {3: Supplement},
  series    = {Philological Monographs},
  number    = {15},
  publisher = {Scholars Press},
  address   = {Atlanta, GA},
  year      = {1986}
}

@book{rupke2008,
  author    = {R{\"u}pke, J{\"o}rg},
  title     = {Fasti Sacerdotum: A Prosopography of Pagan, Jewish, and Christian Religious Officials in the City of Rome, 300 {BC} to {AD} 499},
  translator = {Richardson, David M. B.},
  publisher = {Oxford University Press},
  address   = {Oxford},
  year      = {2008},
  isbn      = {978-0-19-929113-7}
}

@book{zmeskal2009,
  author    = {Zmeskal, Klaus},
  title     = {Adfinitas: Die Verwandtschaften der senatorischen F{\"u}hrungsschicht der r{\"o}mischen Republik von 218--31 v.~Chr.},
  publisher = {Verlag Karl Stutz},
  address   = {Passau},
  year      = {2009},
  isbn      = {978-3-88849-304-1}
}
```

### Citing this tool

If you use dprr-mcp in your research, please cite:

```bibtex
@software{dprr_mcp,
  author    = {Gillis, Andrew},
  title     = {dprr-mcp: Natural Language {SPARQL} Queries for the Digital Prosopography of the Roman Republic},
  year      = {2025},
  url       = {https://github.com/gillisandrew/dprr-mcp}
}
```

## Development

```bash
uv run pytest
uv run ruff check .
```
