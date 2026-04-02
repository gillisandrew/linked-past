# Dataset Lifecycle CLI

## Overview

Add `update`, `reload`, and `reindex` subcommands to `linked-past-server`. Rename the existing `rebuild` to `reindex`. These commands cover the full dataset lifecycle: pull new data from OCI, reload stores from disk after manual edits, and rebuild search/meta-entity caches independently.

## Commands

### `update [datasets...] [--all] [--force]`

Re-pull dataset(s) from OCI, reload the store with materialization, and rebuild search entries for affected datasets.

- Without `--force`: checks OCI digest and skips if unchanged.
- With `--force`: always re-pulls.
- Without dataset args or `--all`: interactive selection (same UX as `init`).

Implementation: for each dataset, calls `registry.initialize_dataset(name, force=True)`, then clears and re-indexes that dataset in the search DB.

### `reload [datasets...] [--all]`

Re-open stores from existing TTL files on disk (no OCI download). Useful after manual TTL edits or external data dir modifications.

Implementation: for each dataset, deletes the store directory, then calls `registry.initialize_dataset(name)` which will re-load from the existing TTL files and run materialization. Then clears and re-indexes that dataset in the search DB.

### `reindex`

Rebuild search DB and meta-entity caches from all existing stores. No data download or store reload. Replaces the current `rebuild` command.

Implementation: identical to current `_cmd_rebuild` — deletes `search.db`, `embeddings.db`, `meta_entities.db`, then calls `build_app_context(eager=False, skip_search=False)`.

### Removed

- `rebuild` — renamed to `reindex`.

## Files Modified

- `packages/linked-past/linked_past/core/server.py` — add `_cmd_update`, `_cmd_reload`, update `main()` arg parser, rename `_cmd_rebuild` → `_cmd_reindex`.
- `packages/linked-past/linked_past/core/search.py` — `clear_dataset` already exists, no changes needed.

## Testing

CLI commands are integration-level (require data dir, OCI access). Test via existing `test_server.py` patterns — verify subcommands are registered on the MCP server's arg parser.
