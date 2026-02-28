# Rename dprr-tool to dprr-mcp

## Overview

Rename the project from `dprr-tool` to `dprr-mcp` to better reflect that this is an MCP server for the DPRR dataset.

## What Changes

**Repository:** `gillisandrew/dprr-tool` -> `gillisandrew/dprr-mcp` (GitHub rename, preserves history)

**Python package:**
- `pyproject.toml` name: `dprr-tool` -> `dprr-mcp`
- Source directory: `dprr_tool/` -> `dprr_mcp/`
- All internal imports: `dprr_tool.` -> `dprr_mcp.`
- All test imports: `dprr_tool.` -> `dprr_mcp.`
- `DEFAULT_DATA_URL` in `fetch.py`: GitHub URL path updated

**References:** CLAUDE.md, README.md, skill files updated.

**Unchanged:** CLI command (`dprr-server`), MCP tool names, skill invocation (`/dprr`), YAML context files, data, scripts.

## Execution Order

1. Rename `dprr_tool/` -> `dprr_mcp/`
2. Update all imports and references across Python files, tests, docs
3. Verify: `uv run pytest -q && uv run ruff check .`
4. Single commit: `refactor: rename dprr-tool to dprr-mcp`
5. Manual: rename repo on GitHub (Settings > General)
