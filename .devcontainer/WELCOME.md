# linked-past

Multi-dataset prosopographical SPARQL tools for AI agents.

## Quick Start

The MCP server starts automatically. Just open a terminal and run:

```bash
claude
```

Claude Code connects to the server via the `.mcp.json` in this repo. Try asking:

```
Who were the consuls of the Roman Republic in 63 BC?
```

If you haven't authenticated yet:

```bash
claude login
```

## Server Management

```bash
# Check server status
curl -s http://localhost:8000/mcp | head -1

# View server logs
tail -f /tmp/linked-past-server.log

# Restart the server
bash .devcontainer/start.sh

# Pull or update a specific dataset
uv run linked-past-server init dprr pleiades

# Check which datasets are installed
uv run linked-past-server status
```

## Datasets

| Dataset | Period | Description |
|---------|--------|-------------|
| DPRR | 509-31 BC | Roman Republic prosopography (persons, offices, families) |
| Pleiades | Archaic-Late Antiquity | Gazetteer of ~41,000 ancient places |
| PeriodO | All periods | Scholarly period definitions with temporal bounds |
| Nomisma | Ancient-modern | Numismatic concepts (people, mints, denominations) |
| CRRO | 280-27 BC | 2,602 Roman Republican coin types (Crawford RRC) |
| OCRE | 31 BC-491 AD | ~50,000 Roman Imperial coin types (RIC) |
| EDH | Antiquity | 81,000+ Latin inscriptions with prosopographic data |

## Development

```bash
uv run pytest              # Run tests
uv run ruff check .        # Lint
uv run linked-past-server  # Start server (foreground)
```
