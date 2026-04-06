# Entity Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pre-resolve entity URIs at server write time so the static viewer can show entity popovers without a backend.

**Architecture:** The server extracts entity URIs from each tool message, resolves them via the existing entity resolution logic, and appends an `entity_cache` message to the JSONL stream. The viewer parses these into a lookup map exposed via React context. `useEntityQuery` checks the cache before fetching from the API. Static mode enables popovers when cache data is available.

**Tech Stack:** Python (server, Oxigraph SPARQL), TypeScript/React (viewer, Zod schemas, React Query, React context)

**Spec:** `docs/superpowers/specs/2026-04-06-entity-cache-design.md`

---

### Task 1: Extract `resolve_entity` from `entity_handler`

**Files:**
- Modify: `packages/linked-past/linked_past/core/viewer_api.py`
- Test: `packages/linked-past/tests/test_resolve_entity.py`

The existing `entity_handler()` (lines 70-245 of `viewer_api.py`) is an HTTP request handler that also contains the entity resolution logic. Extract the resolution logic into a standalone function so the cache builder can call it without an HTTP request.

**IMPORTANT:** This task is a **move/extract refactor**, not a rewrite. The actual SPARQL queries, URI normalization, `execute_query` usage, `registry.dataset_for_uri()` return type (`str | None`), `registry.get_store()` pattern, type hierarchy local-name extraction, and batched `VALUES` predicate meta query must all be preserved exactly as they exist in `entity_handler`. Do NOT rewrite the queries from scratch.

**Key API facts from the actual code:**
- `registry.dataset_for_uri(uri)` returns `str | None` (the dataset name string), NOT a tuple.
- `registry.get_store(ds_name)` returns the Oxigraph store for a dataset.
- All SPARQL queries use `execute_query(store, sparql)` from `linked_past.core.store`, which returns `list[dict[str, str]]`.
- The URI normalization uses `str.replace("://www.", "://")` and maps `edh.ub.uni-heidelberg.de/edh/` to `edh-www.adw.uni-heidelberg.de/edh/` (line 86-89).
- Type hierarchy filters out `http://www.w3.org/` types and extracts local names via `rsplit` (lines 173-178).
- Predicate meta uses a single batched `VALUES` clause query (lines 182-208), NOT individual queries per predicate.
- `description` defaults to `""` (empty string), not `None` (line 108).

- [ ] **Step 1: Write the failing test**

Create `packages/linked-past/tests/test_resolve_entity.py`:

```python
"""Tests for the standalone resolve_entity function."""

import pytest
from unittest.mock import MagicMock, patch

from linked_past.core.viewer_api import resolve_entity


def _make_mock_registry(ds_name: str | None = "dprr"):
    """Create a mock registry that returns ds_name for known URIs.

    Key: registry.dataset_for_uri() returns str | None (dataset name),
    and registry.get_store() returns a store mock.
    """
    store = MagicMock()
    # execute_query returns list[dict[str, str]] — default empty
    store_query_results = []

    registry = MagicMock()
    registry.dataset_for_uri.return_value = ds_name
    registry.get_store.return_value = store

    return registry, store


def test_resolve_entity_returns_none_for_unknown_uri():
    registry = MagicMock()
    registry.dataset_for_uri.return_value = None
    linkage = MagicMock()
    linkage.find_links.return_value = []

    result = resolve_entity("http://unknown.example/thing/1", registry, linkage)
    assert result is None


@patch("linked_past.core.viewer_api.execute_query", return_value=[])
@patch("linked_past.core.server._find_store_xrefs", return_value=[])
def test_resolve_entity_returns_entity_data_dict(mock_xrefs, mock_eq):
    registry, store = _make_mock_registry("dprr")
    linkage = MagicMock()
    linkage.find_links.return_value = []

    result = resolve_entity("http://romanrepublic.ac.uk/person/1", registry, linkage)
    assert result is not None
    assert result["dataset"] == "dprr"
    assert "name" in result
    assert "properties" in result
    assert isinstance(result["properties"], list)
    assert "xrefs" in result
    assert isinstance(result["xrefs"], list)
    # description defaults to "" (empty string), not None
    assert result["description"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_resolve_entity.py -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_entity'`

- [ ] **Step 3: Extract `resolve_entity` function**

In `viewer_api.py`, add a new function before `entity_handler` (before line 70). This function is an extraction of the resolution logic from `entity_handler` lines 82-244. **Move the actual code** — do not rewrite queries.

The function signature:

```python
def resolve_entity(
    uri: str,
    registry,
    linkage,
) -> dict | None:
    """Resolve an entity URI to an EntityData dict, or None if not found.

    This is the core resolution logic shared by the REST endpoint and
    the entity cache builder.
    """
```

The body should contain the exact code currently in `entity_handler` lines 82-244, with these adjustments:
- Replace `mgr.app_context.registry` / `mgr.app_context.linkage` with the `registry` / `linkage` parameters.
- Replace `request.query_params.get("uri")` with the `uri` parameter.
- Use `canonical_uri` as the local variable name (matching the existing code).
- At the end, `return` the dict instead of wrapping in `JSONResponse`.
- Add `from linked_past.core.store import execute_query` at the top of the function body (matching line 116).
- Return `None` if no dataset is found (instead of returning a fallback JSONResponse).

The function must preserve:
- `str.replace("://www.", "://")` normalization (line 84)
- `edh.ub.uni-heidelberg.de/edh/` → `edh-www.adw.uni-heidelberg.de/edh/` mapping (lines 86-89)
- `registry.dataset_for_uri()` returning `str | None` (line 96)
- `registry.get_store(ds_name)` to get the store (line 115)
- `execute_query(store, sparql)` for all SPARQL calls
- The `_query_props` inner function with deduplication (lines 121-136)
- http/https fallback for properties (lines 140-147)
- Type hierarchy filtering `http://www.w3.org/` and local name extraction (lines 173-178)
- Batched `VALUES` clause for predicate meta (lines 182-208)
- `description` defaults to `""` (line 108), NOT `None`
- Cross-reference deduplication by target (lines 220-224)

- [ ] **Step 4: Update `entity_handler` to call `resolve_entity`**

Replace the body of `entity_handler` (lines 70-245) to delegate to `resolve_entity`:

```python
async def entity_handler(request: Request) -> JSONResponse | PlainTextResponse:
    """GET /viewer/api/entity?uri=... — return entity properties + xrefs as JSON."""
    mgr = get_manager()
    if mgr is None or not mgr.is_active:
        return PlainTextResponse("Viewer not active", status_code=404)

    uri = request.query_params.get("uri")
    if not uri:
        return JSONResponse({"error": "Missing 'uri' query parameter"}, status_code=400)
    if not uri.startswith(("http://", "https://")):
        return JSONResponse({"error": "Invalid URI scheme"}, status_code=400)

    registry = mgr.app_context.registry
    linkage = mgr.app_context.linkage

    result = resolve_entity(uri, registry, linkage)
    if result is None:
        return JSONResponse({
            "uri": uri,
            "name": uri.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1],
            "dataset": None,
            "properties": [],
            "xrefs": [],
        })

    return JSONResponse(result)
```

Note: preserve the original error responses (status 404 for inactive viewer, 400 for missing/invalid URI) and the fallback response shape for unknown URIs.

- [ ] **Step 5: Run tests**

Run: `uv run pytest packages/linked-past/tests/test_resolve_entity.py -v`
Expected: PASS (both tests)

Also run: `uv run pytest -q`
Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add packages/linked-past/linked_past/core/viewer_api.py packages/linked-past/tests/test_resolve_entity.py
git commit -m "refactor: extract resolve_entity from entity_handler"
```

---

### Task 2: URI extraction utilities

**Files:**
- Create: `packages/linked-past/linked_past/core/uri_extract.py`
- Test: `packages/linked-past/tests/test_uri_extract.py`

A utility that extracts entity URIs from a viewer message's data dict, given the message type. Used by the cache builder to know which URIs to resolve.

- [ ] **Step 1: Write the failing test**

Create `packages/linked-past/tests/test_uri_extract.py`:

```python
"""Tests for URI extraction from viewer messages."""

import re
from linked_past.core.uri_extract import extract_entity_uris


def test_extract_from_query_rows():
    data = {
        "rows": [
            {"person": "http://romanrepublic.ac.uk/person/1", "name": "Cicero"},
            {"person": "http://romanrepublic.ac.uk/person/2", "name": "Caesar"},
            {"count": 42},
        ],
        "columns": ["person", "name"],
        "sparql": "SELECT ...",
        "row_count": 2,
    }
    uris = extract_entity_uris("query", data)
    assert "http://romanrepublic.ac.uk/person/1" in uris
    assert "http://romanrepublic.ac.uk/person/2" in uris
    assert len(uris) == 2  # "Cicero", "Caesar", 42 are not URIs


def test_extract_from_search_results():
    data = {
        "query_text": "cicero",
        "results": [
            {"uri": "http://romanrepublic.ac.uk/person/1", "label": "Cicero", "dataset": "dprr"},
        ],
    }
    uris = extract_entity_uris("search", data)
    assert uris == {"http://romanrepublic.ac.uk/person/1"}


def test_extract_from_entity_data():
    data = {
        "uri": "http://romanrepublic.ac.uk/person/1",
        "name": "Cicero",
        "dataset": "dprr",
        "properties": [
            {"pred": "http://example.org/hasOffice", "obj": "http://romanrepublic.ac.uk/office/consul"},
            {"pred": "http://example.org/name", "obj": "Marcus Tullius Cicero"},
        ],
        "xrefs": [
            {"target": "http://nomisma.org/id/cicero", "relationship": "skos:closeMatch", "confidence": "confirmed", "basis": "curated"},
        ],
        "see_also": ["http://en.wikipedia.org/wiki/Cicero"],
    }
    uris = extract_entity_uris("entity", data)
    # Should include the entity's own URI, property object URIs, xref targets
    assert "http://romanrepublic.ac.uk/person/1" in uris
    assert "http://romanrepublic.ac.uk/office/consul" in uris
    assert "http://nomisma.org/id/cicero" in uris
    # Literal values and external URIs excluded (see_also are typically external)
    assert "Marcus Tullius Cicero" not in uris
    assert "http://en.wikipedia.org/wiki/Cicero" not in uris


def test_extract_from_links_data():
    data = {
        "uri": "http://romanrepublic.ac.uk/person/1",
        "links": [
            {"target": "http://nomisma.org/id/cicero", "relationship": "skos:closeMatch", "confidence": "confirmed", "basis": "curated"},
        ],
    }
    uris = extract_entity_uris("links", data)
    # Should include the subject URI and link targets
    assert "http://romanrepublic.ac.uk/person/1" in uris
    assert "http://nomisma.org/id/cicero" in uris


def test_extract_from_report_markdown():
    data = {
        "title": "Analysis",
        "markdown": "The entity [Cicero](http://romanrepublic.ac.uk/person/1) held office. See also http://nomisma.org/id/rome for context.",
    }
    uris = extract_entity_uris("report", data)
    assert "http://romanrepublic.ac.uk/person/1" in uris
    assert "http://nomisma.org/id/rome" in uris


def test_extract_returns_empty_for_unknown_type():
    uris = extract_entity_uris("unknown_type", {})
    assert uris == set()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_uri_extract.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `uri_extract.py`**

Create `packages/linked-past/linked_past/core/uri_extract.py`:

```python
"""Extract entity URIs from viewer message data payloads."""

from __future__ import annotations

import re

# URI prefixes we recognise as resolvable entities.
# External URIs (wikipedia, wikidata, etc.) are excluded.
_KNOWN_PREFIXES = (
    "http://romanrepublic.ac.uk/",
    "http://nomisma.org/",
    "http://numismatics.org/crro/",
    "http://numismatics.org/ocre/",
    "https://edh.ub.uni-heidelberg.de/",
    "http://edh-hd.de/",
    "https://pleiades.stoa.org/",
    "http://n2t.net/ark:/99152/",  # PeriodO
    "https://rpc.ashmus.ox.ac.uk/",
)

_URI_RE = re.compile(r"https?://[^\s\)\]\",><]+")


def _is_known(uri: str) -> bool:
    return any(uri.startswith(p) for p in _KNOWN_PREFIXES)


def extract_entity_uris(msg_type: str, data: dict) -> set[str]:
    """Return the set of resolvable entity URIs found in a message's data."""
    uris: set[str] = set()

    if msg_type == "query":
        for row in data.get("rows", []):
            for val in row.values():
                if isinstance(val, str) and _is_known(val):
                    uris.add(val)

    elif msg_type == "search":
        for result in data.get("results", []):
            uri = result.get("uri", "")
            if _is_known(uri):
                uris.add(uri)

    elif msg_type == "entity":
        # The entity's own URI
        entity_uri = data.get("uri", "")
        if _is_known(entity_uri):
            uris.add(entity_uri)
        for prop in data.get("properties", []):
            obj = prop.get("obj", "")
            if _is_known(obj):
                uris.add(obj)
        for xref in data.get("xrefs", []):
            target = xref.get("target", "")
            if _is_known(target):
                uris.add(target)
        # Note: see_also[] are typically external (Wikipedia, Wikidata) — not extracted.
        # They're not resolvable via our datasets.

    elif msg_type == "links":
        # The subject entity's URI
        links_uri = data.get("uri", "")
        if _is_known(links_uri):
            uris.add(links_uri)
        for link in data.get("links", []):
            target = link.get("target", "")
            if _is_known(target):
                uris.add(target)

    elif msg_type == "report":
        md = data.get("markdown", "")
        for m in _URI_RE.finditer(md):
            candidate = m.group(0)
            if _is_known(candidate):
                uris.add(candidate)

    return uris
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/linked-past/tests/test_uri_extract.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past/linked_past/core/uri_extract.py packages/linked-past/tests/test_uri_extract.py
git commit -m "feat: URI extraction utility for entity cache"
```

---

### Task 3: Entity cache builder in `_push_to_viewer`

**Files:**
- Modify: `packages/linked-past/linked_past/core/server.py`
- Modify: `packages/linked-past/linked_past/core/viewer.py`
- Test: `packages/linked-past/tests/test_entity_cache.py`

After each tool message, the server resolves new entity URIs and writes an `entity_cache` message.

- [ ] **Step 1: Add `resolved_uris` tracking to ViewerManager**

In `viewer.py`, add a `_resolved_uris: set[str]` field to `ViewerManager.__init__` (line 34):

```python
def __init__(self, app_context=None) -> None:
    self._clients: set[WebSocket] = set()
    self._active = False
    self._history: list[str] = []
    self._seq = 0
    self._session_id: str | None = None
    self._session_file = None
    self._resolved_uris: set[str] = set()
    self.app_context = app_context
```

Reset it in `activate()` (after line 80, where `_session_id` is set):

```python
self._resolved_uris = set()
```

Add a property:

```python
@property
def resolved_uris(self) -> set[str]:
    return self._resolved_uris
```

- [ ] **Step 2: Write the cache builder test**

Create `packages/linked-past/tests/test_entity_cache.py`:

```python
"""Tests for entity cache generation after viewer pushes."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from linked_past.core.server import _push_to_viewer, AppContext


@pytest.fixture
def mock_app():
    """Create a minimal AppContext with a mock viewer."""
    viewer = MagicMock()
    viewer.is_active = True
    viewer.session_id = "test-session"
    viewer.next_seq.return_value = 1
    viewer.broadcast = AsyncMock()
    viewer.resolved_uris = set()

    registry = MagicMock()
    registry.dataset_for_uri.return_value = None  # default: no match
    registry.get_store.return_value = MagicMock()  # mock store

    linkage = MagicMock()
    linkage.find_links.return_value = []

    app = AppContext(registry=registry, linkage=linkage)
    app.viewer = viewer
    return app


@pytest.mark.asyncio
async def test_push_to_viewer_writes_entity_cache(mock_app):
    """After a query message with entity URIs, an entity_cache message should follow."""
    # Make one URI resolvable — dataset_for_uri returns str | None
    mock_app.registry.dataset_for_uri.side_effect = lambda uri: (
        "dprr" if "romanrepublic" in uri else None
    )

    data = {
        "rows": [{"person": "http://romanrepublic.ac.uk/person/1", "name": "Cicero"}],
        "columns": ["person", "name"],
        "sparql": "SELECT ...",
        "row_count": 1,
    }

    await _push_to_viewer(mock_app, "query", "dprr", data)

    # Should have been called twice: once for the query message, once for entity_cache
    assert mock_app.viewer.broadcast.call_count == 2

    cache_msg = json.loads(mock_app.viewer.broadcast.call_args_list[1][0][0])
    assert cache_msg["type"] == "entity_cache"
    assert "http://romanrepublic.ac.uk/person/1" in cache_msg["data"]["entities"]


@pytest.mark.asyncio
async def test_push_to_viewer_skips_cache_when_no_uris(mock_app):
    """No entity_cache message if no resolvable URIs found."""
    data = {"title": "Report", "markdown": "No entities here."}

    await _push_to_viewer(mock_app, "report", None, data)

    # Only one broadcast: the report message itself
    assert mock_app.viewer.broadcast.call_count == 1


@pytest.mark.asyncio
async def test_push_to_viewer_deduplicates_resolved_uris(mock_app):
    """URIs resolved in earlier messages are not re-resolved."""
    mock_app.viewer.resolved_uris.add("http://romanrepublic.ac.uk/person/1")

    data = {
        "rows": [{"person": "http://romanrepublic.ac.uk/person/1"}],
        "columns": ["person"],
        "sparql": "SELECT ...",
        "row_count": 1,
    }

    await _push_to_viewer(mock_app, "query", "dprr", data)

    # Only one broadcast: the query message. No cache since URI already resolved.
    assert mock_app.viewer.broadcast.call_count == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_entity_cache.py -v`
Expected: FAIL (tests expect 2 broadcasts but only 1 happens)

- [ ] **Step 4: Add entity cache logic to `_push_to_viewer`**

In `server.py`, modify `_push_to_viewer` (lines 487-503). After the existing broadcast, add cache resolution:

```python
async def _push_to_viewer(
    app: AppContext, tool_name: str, dataset: str | None, data: dict
) -> None:
    if app.viewer is None or not app.viewer.is_active:
        return

    import json
    from datetime import datetime, timezone

    message = json.dumps({
        "session_id": app.viewer.session_id,
        "seq": app.viewer.next_seq(),
        "type": tool_name,
        "dataset": dataset,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    })
    logger.debug("Pushing %s message to viewer", tool_name)
    await app.viewer.broadcast(message)

    # --- Entity cache: resolve new URIs found in this message ---
    from linked_past.core.uri_extract import extract_entity_uris
    from linked_past.core.viewer_api import resolve_entity

    found = extract_entity_uris(tool_name, data)
    new_uris = found - app.viewer.resolved_uris
    if not new_uris:
        return

    entities = {}
    for uri in new_uris:
        try:
            entity_data = resolve_entity(uri, app.registry, app.linkage)
        except Exception:
            logger.debug("Failed to resolve entity %s for cache", uri)
            continue
        if entity_data:
            entities[uri] = entity_data
            app.viewer.resolved_uris.add(uri)

    if entities:
        cache_msg = json.dumps({
            "type": "entity_cache",
            "data": {"entities": entities},
        })
        await app.viewer.broadcast(cache_msg)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest packages/linked-past/tests/test_entity_cache.py -v`
Expected: PASS (all 3 tests)

Also run: `uv run pytest -q`
Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add packages/linked-past/linked_past/core/server.py packages/linked-past/linked_past/core/viewer.py packages/linked-past/tests/test_entity_cache.py
git commit -m "feat: entity cache generation after viewer pushes"
```

---

### Task 4: Viewer — EntityCacheSchema and parser changes

**Files:**
- Modify: `packages/linked-past-viewer/src/lib/schemas.ts`
- Modify: `packages/linked-past-viewer/src/lib/parse-session.ts`

- [ ] **Step 1: Add EntityCacheSchema to schemas.ts**

After `ReportDataSchema` (line 64), add:

```typescript
export const EntityCacheDataSchema = z.object({
  entities: z.record(z.string(), EntityDataSchema),
});

export const EntityCacheMessageSchema = z.object({
  type: z.literal("entity_cache"),
  data: EntityCacheDataSchema,
});
```

Add to the exports at the bottom of the file:

```typescript
export type EntityCacheData = z.infer<typeof EntityCacheDataSchema>;
```

- [ ] **Step 2: Update parse-session.ts to collect entity cache**

Modify `ParseResult` type to include entityCache:

```typescript
export type ParseResult = {
  messages: ViewerMessage[];
  errors: ParseError[];
  formatVersion: number | null;
  entityCache: Map<string, EntityData>;
};
```

Add import at top:

```typescript
import { ViewerMessageSchema, SessionMetaSchema, EntityCacheMessageSchema } from "./schemas";
import type { ViewerMessage, EntityData } from "./schemas";
```

In `parseSessionJsonl`, initialize the cache map and check for entity_cache messages before the ViewerMessage validation:

```typescript
export function parseSessionJsonl(text: string): ParseResult {
  const lines = text.split("\n").filter((l) => l.trim());
  const messages: ViewerMessage[] = [];
  const errors: ParseError[] = [];
  let formatVersion: number | null = null;
  const entityCache = new Map<string, EntityData>();

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      errors.push({ line: i + 1, raw, error: `Invalid JSON: ${e}` });
      continue;
    }

    // Session meta preamble
    const metaResult = SessionMetaSchema.safeParse(parsed);
    if (metaResult.success) {
      formatVersion = metaResult.data.format_version;
      continue;
    }

    // Entity cache messages
    const cacheResult = EntityCacheMessageSchema.safeParse(parsed);
    if (cacheResult.success) {
      for (const [uri, data] of Object.entries(cacheResult.data.data.entities)) {
        entityCache.set(uri, data);
      }
      continue;
    }

    // Regular viewer messages
    const msgResult = ViewerMessageSchema.safeParse(parsed);
    if (msgResult.success) {
      messages.push(msgResult.data);
    } else {
      errors.push({
        line: i + 1,
        raw: raw.length > 200 ? raw.slice(0, 200) + "…" : raw,
        error: msgResult.error.issues.map((e) => e.message).join("; "),
      });
    }
  }

  messages.sort((a, b) => a.seq - b.seq);
  return { messages, errors, formatVersion, entityCache };
}
```

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past-viewer/src/lib/schemas.ts packages/linked-past-viewer/src/lib/parse-session.ts
git commit -m "feat(viewer): parse entity_cache messages from JSONL"
```

---

### Task 5: Viewer — Entity cache context

**Files:**
- Create: `packages/linked-past-viewer/src/lib/entity-cache-context.ts`

- [ ] **Step 1: Create the context**

```typescript
import { createContext, useContext } from "react";
import type { EntityData } from "./schemas";

export type EntityCache = Map<string, EntityData>;

const EntityCacheContext = createContext<EntityCache>(new Map());

export const EntityCacheProvider = EntityCacheContext.Provider;

export function useEntityCache(): EntityCache {
  return useContext(EntityCacheContext);
}
```

- [ ] **Step 2: Commit**

```bash
git add packages/linked-past-viewer/src/lib/entity-cache-context.ts
git commit -m "feat(viewer): entity cache React context"
```

---

### Task 6: Viewer — Wire useEntityQuery to check cache first

**Files:**
- Modify: `packages/linked-past-viewer/src/hooks/use-entity-query.ts`

- [ ] **Step 1: Update the hook**

Replace the entire file:

```typescript
import { useQuery } from "@tanstack/react-query";
import type { EntityData } from "../lib/types";
import { useEntityCache } from "../lib/entity-cache-context";

export async function fetchEntity(uri: string): Promise<EntityData> {
  const res = await fetch(`/viewer/api/entity?uri=${encodeURIComponent(uri)}`);
  return res.json();
}

export function useEntityQuery(uri: string, enabled: boolean) {
  const cache = useEntityCache();
  const cached = cache.get(uri);

  return useQuery<EntityData>({
    queryKey: ["entity", uri],
    queryFn: () => fetchEntity(uri),
    staleTime: Infinity,
    enabled: enabled && !cached,
    ...(cached ? { initialData: cached } : {}),
  });
}
```

If the URI is in the cache, `initialData` provides it immediately and `enabled: false` prevents a network fetch. React Query still returns the same `{ data, isLoading }` interface.

- [ ] **Step 2: Commit**

```bash
git add packages/linked-past-viewer/src/hooks/use-entity-query.ts
git commit -m "feat(viewer): useEntityQuery checks cache before fetching"
```

---

### Task 7: Viewer — Wire entity cache into entry points

**Files:**
- Modify: `packages/linked-past-viewer/src/hooks/use-static-session.ts`
- Modify: `packages/linked-past-viewer/src/entries/static.tsx`
- Modify: `packages/linked-past-viewer/src/hooks/use-viewer-socket.ts`
- Modify: `packages/linked-past-viewer/src/components/viewer-layout.tsx`
- Modify: `packages/linked-past-viewer/src/components/entity-uri.tsx`

- [ ] **Step 1: Static entry — populate cache from parsed JSONL**

First, update `use-static-session.ts`. The current `StaticSession` type (lines 6-15) and `applyResult` callback (line 23-28) need to include `entityCache`.

Add import:

```typescript
import type { EntityData } from "@/lib/schemas";
```

Update the `StaticSession` type:

```typescript
export type StaticSession = {
  messages: ViewerMessage[];
  errors: ParseError[];
  formatVersion: number | null;
  entityCache: Map<string, EntityData>;
  loadFromText: (text: string) => void;
  loadFromFile: (file: File) => void;
  loadFromParseResult: (result: ParseResult) => void;
  clear: () => void;
  isLoaded: boolean;
};
```

Add state:

```typescript
const [entityCache, setEntityCache] = useState<Map<string, EntityData>>(new Map());
```

In `applyResult`, add:

```typescript
setEntityCache(result.entityCache);
```

In `clear`, add:

```typescript
setEntityCache(new Map());
```

Return `entityCache` alongside other session state.

Then in `static.tsx`, add import:

```typescript
import { EntityCacheProvider } from "@/lib/entity-cache-context";
```

The `session` hook is called inside `StaticApp`, so the `EntityCacheProvider` goes inside `StaticApp`, wrapping the main return (after the early returns for loading, error, and drop zone):

```tsx
return (
  <EntityCacheProvider value={session.entityCache}>
    <div className="min-h-screen bg-background text-foreground">
      {/* ... existing header and content ... */}
    </div>
  </EntityCacheProvider>
);
```

- [ ] **Step 2: Live entry — handle entity_cache WebSocket messages**

In `use-viewer-socket.ts`, the current `onmessage` handler (line 24-50) combines `JSON.parse` + `ViewerMessageSchema.safeParse` in one line:

```typescript
const parsed = ViewerMessageSchema.safeParse(JSON.parse(e.data));
```

This needs to be restructured to a two-step flow so we can check for `entity_cache` before `ViewerMessage`. Add imports at the top:

```typescript
import { ViewerMessageSchema, EntityCacheMessageSchema } from "../lib/schemas";
import type { EntityData } from "../lib/types";
```

Add a new state for the cache after the existing state declarations:

```typescript
const [entityCache, setEntityCache] = useState<Map<string, EntityData>>(new Map());
```

Replace the `onmessage` handler body (lines 24-50) with:

```typescript
ws.onmessage = (e) => {
  try {
    const raw = JSON.parse(e.data);

    // Check for entity_cache messages first (no seq, not a ViewerMessage)
    const cacheResult = EntityCacheMessageSchema.safeParse(raw);
    if (cacheResult.success) {
      setEntityCache((prev) => {
        const next = new Map(prev);
        for (const [uri, data] of Object.entries(cacheResult.data.data.entities)) {
          next.set(uri, data);
        }
        return next;
      });
      return; // Not a regular message
    }

    // Regular viewer messages
    const parsed = ViewerMessageSchema.safeParse(raw);
    if (!parsed.success) {
      console.warn("Invalid viewer message:", parsed.error.issues[0]?.message);
      return;
    }
    const msg = parsed.data;

    // Detect new session by session_id change
    if (msg.session_id && msg.session_id !== currentSessionId.current) {
      if (currentSessionId.current !== null) {
        seenSeqs.current.clear();
        setMessages([]);
        setEntityCache(new Map());
        clearMessages();
      }
      currentSessionId.current = msg.session_id;
    }

    if (seenSeqs.current.has(msg.seq)) return;
    seenSeqs.current.add(msg.seq);
    setMessages((prev) => [...prev, msg]);
    putMessage(msg);
  } catch {
    console.warn("Failed to parse viewer message:", e.data);
  }
};
```

Note: also clear the entity cache on session change (`setEntityCache(new Map())`).

Return `entityCache` from the hook:

```typescript
return { messages, isConnected, entityCache };
```

In `viewer-layout.tsx`, get `entityCache` from the hook and wrap with provider:

```tsx
const { messages: liveMessages, isConnected, entityCache } = useViewerSocket();
```

Wrap the return JSX with `EntityCacheProvider`:

```tsx
return (
  <EntityCacheProvider value={entityCache}>
    <div className="min-h-screen bg-background text-foreground">
      {/* ... existing content ... */}
    </div>
  </EntityCacheProvider>
);
```

In `main.tsx`, no changes needed — the provider is inside `ViewerLayout`.

- [ ] **Step 3: Enable popovers in static mode when cache data is available**

In `entity-uri.tsx`, the static mode branch (lines 39-44) returns a plain `<a>` without a popover. Change it to check the cache and show a popover if data is available:

Replace the static mode early return with logic that falls through to the popover branch when cache data exists:

```typescript
const isStatic = useIsStaticMode();
const [open, setOpen] = useState(false);
const { data, isLoading } = useEntityQuery(uri, open);
const label = display ?? shortUri(uri);

// In static mode without cache data, render as plain link
if (isStatic && !data) {
  return (
    <a href={linkHref(uri)} target="_blank" rel="noopener noreferrer" title={uri}>
      {link}
    </a>
  );
}

// Both live mode and static-with-cache reach here — render popover
```

The rest of the component (the Popover branch) stays unchanged. `useEntityQuery` already returns cached data via `initialData` when available, so `data` will be populated even in static mode if the URI is in the cache.

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past-viewer/src/entries/static.tsx packages/linked-past-viewer/src/entries/main.tsx packages/linked-past-viewer/src/hooks/use-viewer-socket.ts packages/linked-past-viewer/src/hooks/use-static-session.ts packages/linked-past-viewer/src/components/viewer-layout.tsx packages/linked-past-viewer/src/components/entity-uri.tsx
git commit -m "feat(viewer): wire entity cache into both entry points, enable static popovers"
```

---

### Task 8: Integration test

**Files:**
- Modify: `packages/linked-past/tests/test_server.py` or create `packages/linked-past/tests/test_entity_cache_integration.py`

- [ ] **Step 1: Write an integration test**

Test that a full tool call → viewer push → entity cache cycle works end-to-end:

```python
"""Integration test: tool call produces entity_cache message."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from linked_past.core.server import _push_to_viewer, AppContext


@pytest.mark.asyncio
async def test_query_with_entity_uris_produces_cache():
    """A query containing entity URIs should produce an entity_cache broadcast."""
    # Setup: a viewer that captures broadcasts
    broadcasts = []
    viewer = MagicMock()
    viewer.is_active = True
    viewer.session_id = "integration-test"
    viewer.next_seq.return_value = 1
    viewer.resolved_uris = set()

    async def capture_broadcast(msg):
        broadcasts.append(json.loads(msg))

    viewer.broadcast = capture_broadcast

    # Setup: a registry that can resolve one URI
    # Note: dataset_for_uri returns str | None (dataset name), NOT a tuple
    store = MagicMock()

    registry = MagicMock()
    registry.dataset_for_uri.side_effect = lambda uri: (
        "dprr" if "romanrepublic" in uri else None
    )
    registry.get_store.return_value = store

    linkage = MagicMock()
    linkage.find_links.return_value = []

    app = AppContext(registry=registry, linkage=linkage)
    app.viewer = viewer

    # Act: push a query message containing an entity URI
    await _push_to_viewer(app, "query", "dprr", {
        "rows": [{"person": "http://romanrepublic.ac.uk/person/1"}],
        "columns": ["person"],
        "sparql": "SELECT ...",
        "row_count": 1,
    })

    # Assert: two broadcasts — query message + entity_cache
    assert len(broadcasts) == 2
    assert broadcasts[0]["type"] == "query"
    assert broadcasts[1]["type"] == "entity_cache"
    assert "http://romanrepublic.ac.uk/person/1" in broadcasts[1]["data"]["entities"]

    # Assert: URI marked as resolved
    assert "http://romanrepublic.ac.uk/person/1" in viewer.resolved_uris
```

- [ ] **Step 2: Run test**

Run: `uv run pytest packages/linked-past/tests/test_entity_cache_integration.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -q`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past/tests/test_entity_cache_integration.py
git commit -m "test: entity cache integration test"
```
