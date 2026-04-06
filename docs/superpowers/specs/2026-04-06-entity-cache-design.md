# Entity Cache for Offline Popovers

**Date:** 2026-04-06
**Status:** Approved
**Scope:** Server-side entity pre-resolution + viewer cache integration

## Problem

Entity URI popovers don't work in the static viewer. The live viewer fetches entity data on hover via `GET /viewer/api/entity?uri=...`, but the static viewer has no backend. Entity URIs render as plain `<a>` links with no preview.

## Solution

The server pre-resolves entity URIs at write time — when a tool call produces a message containing entity URIs, the server resolves them and appends an `entity_cache` message to the JSONL stream. The viewer reads these into a lookup table and serves popovers from it. Both live and static viewers benefit.

## JSONL Format

A new `entity_cache` message type, interleaved after tool messages:

```jsonl
{"session_id":"...","seq":5,"type":"query","dataset":"dprr","timestamp":"...","data":{...}}
{"type":"entity_cache","data":{"entities":{"http://romanrepublic.ac.uk/person/1234":{...},"http://nomisma.org/id/rome":{...}}}}
{"session_id":"...","seq":6,"type":"entity","dataset":"dprr","timestamp":"...","data":{...}}
```

### entity_cache message shape

```typescript
{
  type: "entity_cache";
  data: {
    entities: Record<string, EntityData>;
  };
}
```

- No `seq`, `session_id`, `dataset`, or `timestamp` — it's metadata, not a tool call.
- Old viewers ignore it (unknown type, no `seq`, fails ViewerMessage validation harmlessly).
- `EntityData` is the same schema already used by `explore_entity` responses and the `/viewer/api/entity` endpoint.

### Backward compatibility

- `format_version` stays at 1. The `entity_cache` message is additive.
- Parsers that validate with `ViewerMessageSchema` (discriminated union on `type`) skip unknown types via the existing error-collection path in `parseSessionJsonl`.

## Server Side

### Where resolution happens

In `_push_to_viewer()` (or a new helper called from it) in `server.py`. After writing the tool message, the server:

1. Extracts entity URIs from the message's `data` payload.
2. Filters out URIs already resolved in this session (tracked per-session in a `Set[str]`).
3. For each new URI, calls the same resolution logic used by `viewer_api.py:entity_handler()` — property query, type hierarchy, cross-references, description, see-also.
4. Writes an `entity_cache` message containing the resolved entities.
5. Pushes the `entity_cache` message over WebSocket to live viewers.

### URI extraction by message type

| Message type | Where URIs appear |
|---|---|
| `query` | Cell values in `data.rows` — strings matching known dataset URI prefixes |
| `search` | `data.results[].uri` |
| `entity` | `data.properties[].obj`, `data.xrefs[].target`, `data.see_also[]`, `data.uri` |
| `links` | `data.links[].target`, `data.uri` |
| `report` | HTTP(S) URLs in `data.markdown` matching known dataset URI prefixes |

A URI is "known" if `registry.dataset_for_uri(uri)` returns a dataset. External URIs (Wikipedia, Wikidata, etc.) are not resolved — they're outside our data.

### Entity resolution

Reuse the existing resolution logic from `viewer_api.py:entity_handler()`. This function:

- Canonicalizes the URI (strips www, tries http/https variants)
- Finds the home dataset via `registry.dataset_for_uri()`
- Queries the dataset store for properties, type hierarchy, description, see-also, cross-references
- Returns `EntityData`

Extract the core resolution into a shared function (e.g., `resolve_entity(registry, linkage, uri) -> EntityData | None`) that both `entity_handler` and the cache builder call.

### Deduplication

The server tracks resolved URIs per session in a `Set[str]` on the `ViewerManager` session state. An entity resolved for message #2 is not re-resolved for message #7. The set resets when a new session starts.

### Performance

- Typical session: 50–200 unique entity URIs.
- Each resolution: 3–5 SPARQL queries against a local Oxigraph store (~1–5ms each).
- Total overhead per tool call: 50–500ms for 10–50 new URIs.
- This runs after the tool response is already sent to the client, so it doesn't add latency to the MCP tool call itself. The entity_cache message arrives asynchronously.

## Viewer Side

### Parser changes (`parse-session.ts`)

`parseSessionJsonl()` currently skips lines that fail `ViewerMessageSchema` validation (collected as errors). Add a pre-check: if a parsed JSON line has `type: "entity_cache"`, validate it with a new `EntityCacheSchema` and collect entities into a `Map<string, EntityData>`.

Return the map alongside messages: `{ messages, errors, formatVersion, entityCache }`.

### Entity cache context

A new React context (`EntityCacheProvider`) that holds a `Map<string, EntityData>`. Both the live and static entry points wrap their component tree with it.

- **Static viewer:** Populated from `parseSessionJsonl()` result at load time.
- **Live viewer:** Starts empty. When an `entity_cache` WebSocket message arrives, merge its entities into the map.

### useEntityQuery changes

Current behavior:
- Live mode: fetches from `/viewer/api/entity?uri=...`
- Static mode: returns nothing (no network)

New behavior:
1. Check entity cache context first. If the URI is in the cache, return the cached `EntityData` immediately (no fetch, no loading state).
2. If not cached and in live mode, fetch from the API as before.
3. If not cached and in static mode, return `null` (no network available).

### entity-uri.tsx changes

Currently, static mode renders a plain `<a>` tag with no popover. After this change, if the entity cache has data for the URI, static mode renders the same popover as live mode. The `useIsStaticMode()` guard that bypasses popovers needs to be relaxed — show the popover if cache data is available, regardless of mode.

## What Does NOT Change

- Live viewer popover behavior for uncached URIs (still fetches from API)
- JSONL format version number
- Static viewer file loading flow (just parses one more message type)
- Entity resolution logic (reused, not rewritten)
- MCP tool response latency (cache is written asynchronously after the tool response)

## Files to Modify

### Server (Python)

| File | Change |
|---|---|
| `packages/linked-past/linked_past/core/viewer_api.py` | Extract `resolve_entity()` from `entity_handler()` |
| `packages/linked-past/linked_past/core/server.py` | Call URI extraction + resolution after `_push_to_viewer()`, write entity_cache message |
| `packages/linked-past/linked_past/core/viewer.py` | Track resolved URIs per session in `Set[str]` |

### Viewer (TypeScript)

| File | Change |
|---|---|
| `src/lib/schemas.ts` | Add `EntityCacheSchema` |
| `src/lib/parse-session.ts` | Parse entity_cache messages, return entityCache map |
| `src/lib/entity-cache-context.ts` | New file: React context for entity cache |
| `src/hooks/use-entity-query.ts` | Check cache context before fetching |
| `src/hooks/use-viewer-socket.ts` | Handle entity_cache WebSocket messages, merge into cache |
| `src/components/entity-uri.tsx` | Show popover in static mode when cache data available |
| `src/entries/main.tsx` | Wrap with EntityCacheProvider |
| `src/entries/static.tsx` | Wrap with EntityCacheProvider, populate from parsed cache |
