# dprr-tool

Natural language SPARQL queries for the [Digital Prosopography of the Roman Republic](http://romanrepublic.ac.uk/) (DPRR). Ask questions about ~4,800 Roman individuals (509–31 BC) — their offices, family relationships, social statuses, and life dates — and get validated SPARQL queries and academic prose summaries.

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

### Load DPRR data

Download the DPRR RDF dataset (Turtle format), then initialize the local Oxigraph store:

```bash
dprr-tool init /path/to/dprr-data.ttl
```

## Usage

### CLI

```bash
# Ask a natural language question (uses Anthropic API)
dprr-tool ask "Who were the consuls in 100 BC?"

# Execute a raw SPARQL query
dprr-tool query "SELECT ?p WHERE { ?p a vocab:Person } LIMIT 10"

# Show store statistics
dprr-tool info
```

### MCP Server

The MCP server supports two transport modes:

- **stdio** (default) — one server per connection, suitable for single-client usage
- **HTTP** (streamable-http) — a single long-running server that multiple clients connect to, ideal for parallel agent workflows

#### stdio mode

Run as an MCP server over stdio for use with Claude Code, Claude Desktop, Cursor, or any MCP-compatible client:

```bash
dprr-server
# or
dprr-tool serve
```

#### HTTP mode

Start a persistent HTTP server that multiple agents can share concurrently:

```bash
dprr-server --transport http
# Custom host/port:
dprr-server --transport http --host 0.0.0.0 --port 9000
```

The server listens on `http://127.0.0.1:8000/mcp` by default. Queries that exceed the timeout (default 30s, configurable via `DPRR_QUERY_TIMEOUT`) return a structured error instead of crashing the connection.

#### MCP Tools

| Tool | Description |
|------|-------------|
| `get_schema` | Returns DPRR ontology prefixes, ShEx schema, and 22 curated example query pairs |
| `validate_sparql` | Syntax check, auto-repairs missing PREFIX declarations, semantic validation against the ontology |
| `execute_sparql` | Full validation + execution against the local Oxigraph RDF store |

#### Claude Code configuration

**HTTP mode** (recommended for parallel agents) — start the server first, then configure Claude Code to connect:

```bash
uv run dprr-server --transport http
```

Add to `.claude/settings.json`:

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

**stdio mode** — Claude Code launches and manages the server process:

```json
{
  "mcpServers": {
    "dprr": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/dprr-tool", "dprr-server"],
      "env": {
        "DPRR_RDF_FILE": "/path/to/dprr-data.ttl"
      }
    }
  }
}
```

Setting `DPRR_RDF_FILE` enables auto-initialization — the store loads the data on first use without needing `dprr-tool init`.

#### Claude Desktop configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dprr": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/dprr-tool", "dprr-server"],
      "env": {
        "DPRR_RDF_FILE": "/path/to/dprr-data.ttl"
      }
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
               │ MCP protocol (stdio or HTTP)
┌──────────────▼──────────────────────┐
│  MCP Server (dprr-server)           │  3 tools: get_schema, validate_sparql,
│  Python, stdio or streamable-http   │  execute_sparql
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Local Oxigraph Store               │  RDF triples from DPRR dataset
└─────────────────────────────────────┘
```

The CLI `ask` command uses the Anthropic API directly for a standalone experience. The MCP server + skill path lets Claude itself orchestrate the pipeline with no API calls needed.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Required for `dprr-tool ask` (CLI mode) |
| `DPRR_STORE_PATH` | Override default store location (`~/.dprr-tool`) |
| `DPRR_RDF_FILE` | Path to DPRR Turtle file for auto-initialization (MCP mode) |
| `DPRR_QUERY_TIMEOUT` | Query timeout in seconds (default: 30) |

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

If you use dprr-tool in your research, please cite:

```bibtex
@software{dprr_tool,
  author    = {Gillis, Andrew},
  title     = {dprr-tool: Natural Language {SPARQL} Queries for the Digital Prosopography of the Roman Republic},
  year      = {2025},
  url       = {https://github.com/gillisandrew/dprr-tool}
}
```

## Development

```bash
uv run pytest
```
