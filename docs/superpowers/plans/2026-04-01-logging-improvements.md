# Logging Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix silent exception handlers, promote under-leveled log messages, add audit logging to MCP tool handlers, add logging to unlogged modules, and remove dead loggers.

**Architecture:** No new modules — all changes are to existing files. The MCP tool handlers in server.py get structured audit logging (tool name, args, duration, result summary). Under-leveled messages in registry.py and meta_entities.py get promoted to `warning`. Silent `except: pass` blocks get `logger.debug`. Dead loggers in 4 files are removed. Modules doing significant work (linkage.py, disambiguate.py, search.py) get loggers and key-point logging.

**Tech Stack:** Python stdlib `logging`

---

### Task 1: Fix Silent Exception Handlers

Two `except: pass` blocks silently swallow errors. Add debug-level logging so failures are diagnosable.

**Files:**
- Modify: `packages/linked-past/linked_past/core/viewer.py:94-97`
- Modify: `packages/linked-past/linked_past/core/viewer_api.py:55-56`

- [ ] **Step 1: Fix viewer.py silent except**

In `packages/linked-past/linked_past/core/viewer.py`, replace:

```python
            try:
                await ws.close()
            except Exception:
                pass
```

With:

```python
            try:
                await ws.close()
            except Exception as e:
                logger.debug("WebSocket close failed: %s", e)
```

- [ ] **Step 2: Fix viewer_api.py silent except**

In `packages/linked-past/linked_past/core/viewer_api.py`, replace:

```python
        except Exception:
            pass
```

With:

```python
        except Exception as e:
            logger.debug("Label query failed for %s: %s", uri, e)
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest -x -v`
Expected: All PASS (logging-only changes).

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past/linked_past/core/viewer.py packages/linked-past/linked_past/core/viewer_api.py
git commit -m "fix: log silently swallowed exceptions in viewer modules"
```

---

### Task 2: Promote Under-Leveled Log Messages

Three `logger.debug()` calls should be `logger.warning()` because they indicate missing data that degrades functionality.

**Files:**
- Modify: `packages/linked-past/linked_past/core/registry.py:183,205`
- Modify: `packages/linked-past/linked_past/core/meta_entities.py:257`

- [ ] **Step 1: Promote VoID load failure to warning**

In `packages/linked-past/linked_past/core/registry.py:183`, replace:

```python
            logger.debug("Could not load VoID for %s: %s", name, e)
```

With:

```python
            logger.warning("Could not load VoID for %s: %s (validation hints unavailable)", name, e)
```

- [ ] **Step 2: Promote schema load failure to warning**

In `packages/linked-past/linked_past/core/registry.py:205`, replace:

```python
            logger.debug("Could not load schema for %s: %s", name, e)
```

With:

```python
            logger.warning("Could not load auto-schema for %s: %s (auto-detected classes unavailable)", name, e)
```

- [ ] **Step 3: Promote DPRR property fetch failure to warning**

In `packages/linked-past/linked_past/core/meta_entities.py:257`, replace:

```python
                logger.debug("Failed to get DPRR properties for %s: %s", dprr_uri, e)
```

With:

```python
                logger.warning("Failed to get DPRR properties for %s: %s", dprr_uri, e)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest -x -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/registry.py packages/linked-past/linked_past/core/meta_entities.py
git commit -m "fix: promote under-leveled log messages to warning"
```

---

### Task 3: Remove Dead Loggers

Four modules create `logger = logging.getLogger(__name__)` but never use it. Remove to avoid confusion.

**Files:**
- Modify: `packages/linked-past/linked_past/core/store.py`
- Modify: `packages/linked-past/linked_past/core/fetch.py`
- Modify: `packages/linked-past/linked_past/core/extraction.py`
- Modify: `packages/linked-past/linked_past/datasets/base.py`

- [ ] **Step 1: Remove dead logger from store.py**

In `packages/linked-past/linked_past/core/store.py`, remove:

```python
import logging
```

and:

```python
logger = logging.getLogger(__name__)
```

(Keep the `import re` that was added for `execute_ask`.)

- [ ] **Step 2: Remove dead logger from fetch.py**

In `packages/linked-past/linked_past/core/fetch.py`, remove:

```python
import logging
```

and:

```python
logger = logging.getLogger(__name__)
```

- [ ] **Step 3: Remove dead logger from extraction.py**

In `packages/linked-past/linked_past/core/extraction.py`, remove:

```python
import logging
```

and:

```python
logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Remove dead logger from base.py**

In `packages/linked-past/linked_past/datasets/base.py`, remove:

```python
import logging
```

and:

```python
logger = logging.getLogger(__name__)
```

- [ ] **Step 5: Run lint and tests**

Run: `uv run ruff check . && uv run pytest -x -v`
Expected: Lint clean, all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/linked-past/linked_past/core/store.py packages/linked-past/linked_past/core/fetch.py packages/linked-past/linked_past/core/extraction.py packages/linked-past/linked_past/datasets/base.py
git commit -m "cleanup: remove dead loggers from 4 modules"
```

---

### Task 4: Add Logging to Linkage Module

`linkage.py` loads YAML and Turtle files with no logging. Add info-level logging for loads and warnings for failures.

**Files:**
- Modify: `packages/linked-past/linked_past/core/linkage.py`

- [ ] **Step 1: Add logger and log messages**

At the top of `packages/linked-past/linked_past/core/linkage.py`, after the imports, add:

```python
import logging

logger = logging.getLogger(__name__)
```

In `load_yaml()` (around line 38-43), after `self._load_data(data)`, add:

```python
        logger.info("Loaded %d links from %s", len(data.get("links", [])), path.name)
```

In `load_rdf_file()` (around line 49-63), after the `added = len(self._store) - before` line, add:

```python
        logger.info("Loaded %d triples from %s", added, path.name)
```

In `_load_data()` (around line 68-73), after the `raise ValueError(...)` line for unknown relationships, the error is already raised. No change needed there.

- [ ] **Step 2: Run tests**

Run: `uv run pytest packages/linked-past/tests/test_linkage.py -v`
Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past/linked_past/core/linkage.py
git commit -m "feat: add logging to linkage module for YAML/RDF loads"
```

---

### Task 5: Add Logging to Disambiguate Module

`disambiguate.py` (623 lines) runs a multi-signal scoring pipeline with no logging. Add info-level logging for the top-level entry point and debug-level for signal scoring. Note: `rank_candidates` is a method on `PersonDisambiguator`, and `CandidateMatch` uses `dprr_uri` (not `uri`).

**Files:**
- Modify: `packages/linked-past/linked_past/core/disambiguate.py`

- [ ] **Step 1: Add logger**

At the top of `packages/linked-past/linked_past/core/disambiguate.py`, after the existing imports, add:

```python
import logging

logger = logging.getLogger(__name__)
```

- [ ] **Step 2: Add logging to PersonDisambiguator.rank_candidates**

This is a method on `PersonDisambiguator` (line 267). Its signature is:
```python
def rank_candidates(self, candidates_signals: list[tuple[str, str, dict[str, SignalResult]]]) -> list[CandidateMatch]:
```

At the start of `rank_candidates` (after the docstring, before `scored = []`), add:

```python
        logger.info("rank_candidates: scoring %d candidates", len(candidates_signals))
```

At the end of `rank_candidates`, before `return results` (line 294), add:

```python
        if results:
            logger.info(
                "rank_candidates: top=%s score=%.3f confidence=%s",
                results[0].dprr_uri, results[0].score, results[0].confidence,
            )
```

- [ ] **Step 3: Add logging to SPARQL fetchers**

`fetch_dprr_candidates` (line 511) returns `execute_query(...)` directly with no intermediate variable. Introduce one:

Replace line 530:
```python
    return execute_query(dprr_store, sparql)
```
With:
```python
    rows = execute_query(dprr_store, sparql)
    logger.debug("fetch_dprr_candidates: %d rows for nomen=%s", len(rows), nomen)
    return rows
```

In `fetch_dprr_offices` (line 533), after `rows = execute_query(dprr_store, sparql)` (line 548), add:
```python
    logger.debug("fetch_dprr_offices: %d rows for %s", len(rows), person_uri)
```

In `fetch_dprr_family` (line 555), after `rows = execute_query(dprr_store, sparql)` (line 588), add:
```python
    logger.debug("fetch_dprr_family: %d rows for %s", len(rows), person_uri)
```

In `fetch_dprr_province_pleiades` (line 600), after `rows = execute_query(dprr_store, sparql)` (line 613), add:
```python
    logger.debug("fetch_dprr_province_pleiades: %d rows for %s", len(rows), person_uri)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/linked-past/tests/test_disambiguate.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/disambiguate.py
git commit -m "feat: add logging to disambiguation pipeline"
```

---

### Task 6: Add Audit Logging to MCP Tool Handlers

`server.py` already has `_log_tool_call` (line 360) which appends structured entries to the in-memory session log. But this only runs on the **success path** and produces no `logger.*` output. Two handlers (`disambiguate`, `update_dataset`) don't call it at all, and **error paths** (timeout, store error, unexpected exception) in `query` are completely silent.

The fix: (1) add a `logger.info` call inside `_log_tool_call` so every successful tool call emits a structured log line, (2) add `_log_tool_call` to the two handlers that lack it, (3) add `logger.warning`/`logger.error` to error paths.

**Files:**
- Modify: `packages/linked-past/linked_past/core/server.py`

- [ ] **Step 1: Emit logger.info from _log_tool_call**

In `_log_tool_call` (line 360), after `app.session_log.append(entry)` (line 384), add:

```python
    logger.info(
        "tool=%s dataset=%s duration=%dms output_len=%d",
        tool_name, inputs.get("dataset"), duration_ms, len(result),
    )
```

This gives every tool call that already uses `_log_tool_call` (query, search_entities, explore_entity, find_links) a structured log line for free.

- [ ] **Step 2: Add error-path logging to `query` handler**

In the `query` handler's except blocks, add logging before each return:

In the `except asyncio.TimeoutError` block (line 709-710), before the return, add:

```python
            logger.warning("tool=query dataset=%s timeout after %ds", dataset, effective_timeout)
```

In the `except OSError as e` block (line 711-712), before the return, add:

```python
            logger.error("tool=query dataset=%s store_error: %s", dataset, e)
```

In the `except Exception as e` block (line 713-714), before the return, add:

```python
            logger.error("tool=query dataset=%s error: %s", dataset, e)
```

- [ ] **Step 3: Add _log_tool_call to `disambiguate` handler**

The `disambiguate` handler (line 1307) has no `_log_tool_call` and no `t0`. Add `t0 = time.monotonic()` after `app: AppContext = ...` (line 1347). Before `return "\n".join(lines)` (line 1485), add:

```python
        _log_tool_call(app, "disambiguate", {"name": name, "uri": uri}, "\n".join(lines), int((time.monotonic() - t0) * 1000))
```

(Note: the handler uses `name` and `uri` as parameter names — both are valid inputs to log.)

- [ ] **Step 4: Add _log_tool_call to `update_dataset` handler**

The `update_dataset` handler (line 1211) has no `_log_tool_call` and no `t0`. Add `t0 = time.monotonic()` after `registry = app.registry` (line 1214). Before `return "\n".join(lines)` (line 1282), add:

```python
        output = "\n".join(lines)
        _log_tool_call(app, "update_dataset", {"dataset": dataset, "force": force}, output, int((time.monotonic() - t0) * 1000))
        return output
```

And change the existing `return "\n".join(lines)` to just use the `output` variable (already captured above).

- [ ] **Step 5: Run tests**

Run: `uv run pytest -x -v`
Expected: All PASS.

- [ ] **Step 6: Run lint**

Run: `uv run ruff check .`
Expected: Clean.

- [ ] **Step 7: Commit**

```bash
git add packages/linked-past/linked_past/core/server.py
git commit -m "feat: add structured audit logging to MCP tool handlers"
```

---

### Task 7: Add Logging to Search Module

`search.py` does SQLite FTS5 operations with no logging.

**Files:**
- Modify: `packages/linked-past/linked_past/core/search.py`

- [ ] **Step 1: Add logger and log messages**

At the top of `packages/linked-past/linked_past/core/search.py`, after the existing imports, add:

```python
import logging

logger = logging.getLogger(__name__)
```

In the `add_batch` method (line 61), after `self._conn.commit()` and before `return len(rows)`, add:

```python
        logger.debug("indexed %d documents dataset=%s", len(rows), rows[0][0] if rows else "?")
```

Note: the parameter is `rows` (not `batch`), typed as `list[tuple[str, str, str]]` where `rows[0][0]` is the dataset name.

In the `search` method (line 74), the return is a list comprehension at lines 123-126. Capture it in a variable first. Replace:

```python
        return [
            {"dataset": ds, "doc_type": dt, "text": text, "score": -score}
            for ds, dt, text, score in rows
        ]
```

With:

```python
        results = [
            {"dataset": ds, "doc_type": dt, "text": text, "score": -score}
            for ds, dt, text, score in rows
        ]
        logger.debug("search query=%r dataset=%s results=%d", query, dataset, len(results))
        return results
```

In `clear_dataset` (line 128), after `self._conn.commit()` and before `return cursor.rowcount`, add:

```python
        logger.info("cleared search index dataset=%s count=%d", dataset, cursor.rowcount)
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest packages/linked-past/tests/test_search.py -v`
Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past/linked_past/core/search.py
git commit -m "feat: add logging to search index operations"
```

---

## Summary

| Task | What | Severity |
|------|------|----------|
| 1 | Fix 2 silent `except: pass` blocks | High |
| 2 | Promote 3 `debug` → `warning` messages | Medium |
| 3 | Remove 4 dead loggers | Low |
| 4 | Add logging to linkage module | Medium |
| 5 | Add logging to disambiguate module | Medium |
| 6 | Add audit logging to MCP tool handlers | High |
| 7 | Add logging to search module | Low |
