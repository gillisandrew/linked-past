# Welcome to linked-past

Multi-dataset prosopographical SPARQL tools for AI agents.

## Getting Started

### 1. Install Claude Code

Open a terminal and run:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Then authenticate:

```bash
claude login
```

### 2. Start the MCP server

```bash
uv run linked-past-server
```

The server starts on `http://localhost:8000/mcp`. On first run, it loads any cached datasets. Use the `update_dataset` MCP tool to pull new datasets from OCI.

### 3. Connect Claude Code

The `.mcp.json` in this repo is already configured. Just run:

```bash
claude
```

Claude Code will connect to the server automatically. Try:

```
Who were the consuls of the Roman Republic in 63 BC?
```

## Available Datasets

| Dataset | Description | Status |
|---------|-------------|--------|
| DPRR | Roman Republic prosopography | Pull via `update_dataset` |
| Pleiades | Ancient places gazetteer | Pull via `update_dataset` |
| PeriodO | Period definitions | Pull via `update_dataset` |
| Nomisma | Numismatic concepts | Pull via `update_dataset` |
| CRRO | Republican coin types | Pull via `update_dataset` |
| EDH | Latin inscriptions | Pull via `update_dataset` |

## Useful Commands

```bash
uv run pytest              # Run tests
uv run ruff check .        # Lint
uv run linked-past-server  # Start MCP server
```
