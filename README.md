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

Run as an MCP server over stdio for use with Claude Code, Claude Desktop, Cursor, or any MCP-compatible client:

```bash
dprr-tool serve
```

#### MCP Tools

| Tool | Description |
|------|-------------|
| `get_schema` | Returns DPRR ontology prefixes, ShEx schema, and 22 curated example query pairs |
| `validate_sparql` | Syntax check, auto-repairs missing PREFIX declarations, semantic validation against the ontology |
| `execute_sparql` | Full validation + execution against the local Oxigraph RDF store |

#### Claude Code configuration

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "dprr": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/dprr-tool", "dprr-tool", "serve"],
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
      "args": ["run", "--directory", "/path/to/dprr-tool", "dprr-tool", "serve"],
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
               │ MCP protocol (stdio)
┌──────────────▼──────────────────────┐
│  MCP Server (dprr-tool serve)       │  3 tools: get_schema, validate_sparql,
│  Python, stdio transport            │  execute_sparql
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

## Development

```bash
uv run pytest
```
