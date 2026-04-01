# Result Viewer Design

A browser-based live results viewer for the linked-past MCP server. Displays query results, entity cards, and cross-references in a scrollable feed that updates in real-time as the user queries through Claude.

## Architecture

```
User: "show me the results visually"
  → LLM calls start_viewer()
    → Server mounts /viewer and /viewer/ws on the Starlette app
    → Returns URL: http://localhost:8000/viewer
    → User opens in browser, WebSocket connects

Subsequent tool calls (query, explore_entity, find_links, etc.):
  → _log_tool_call() fires after each tool execution
  → If viewer is active: render result as HTML fragment
  → Push fragment over WebSocket to all connected browsers
  → Client JS appends to feed, auto-scrolls to newest

User: "stop the viewer"
  → LLM calls stop_viewer()
  → WebSocket connections closed, routes unmounted
```

### Key Principles

- **Opt-in via tool call.** The viewer is not always-on. `start_viewer()` mounts the routes, `stop_viewer()` tears them down. When inactive, zero overhead.
- **Side-channel, not replacement.** Existing tool text output is unchanged. The viewer is a parallel visual stream — Claude still sees markdown, the browser shows styled HTML.
- **No separate process.** Routes are mounted on the existing MCP server's Starlette app (port 8000). No shell scripts, no npm, no build step.
- **Feed layout.** Results accumulate in a scrollable feed, newest at bottom with auto-scroll. Older results are de-emphasized (collapsed) but still accessible.

## File Structure

| File | Purpose |
|---|---|
| `linked_past/core/viewer.py` | Viewer lifecycle (start/stop), WebSocket manager, Starlette route handlers |
| `linked_past/core/viewer_render.py` | HTML fragment renderers — entity cards, tables, result containers |
| `linked_past/core/viewer_page.py` | Self-contained HTML/CSS/JS page as a Python string constant |

Changes to existing files:

| File | Change |
|---|---|
| `linked_past/core/server.py` | Add `start_viewer`/`stop_viewer` tools; hook `_log_tool_call()` to push to viewer; add `viewer` field to `AppContext` |

## MCP Tools

### `start_viewer()`

- Mounts `/viewer` (GET — serves the HTML page) and `/viewer/ws` (WebSocket) on the Starlette app
- Returns `"Viewer started at http://localhost:8000/viewer"`
- If already started, returns the URL without re-mounting
- Stores the WebSocket manager instance on `AppContext.viewer`

### `stop_viewer()`

- Closes all WebSocket connections gracefully
- Unmounts `/viewer` and `/viewer/ws` routes
- Sets `AppContext.viewer = None`
- Returns `"Viewer stopped."`
- If not running, returns `"Viewer is not running."`

## WebSocket Manager (`viewer.py`)

Manages the set of connected browser clients and broadcasts HTML fragments.

```python
class ViewerManager:
    def __init__(self):
        self._clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.add(ws)

    async def disconnect(self, ws: WebSocket):
        self._clients.discard(ws)

    async def broadcast(self, html_fragment: str):
        """Send an HTML fragment to all connected browsers."""
        disconnected = set()
        for ws in self._clients:
            try:
                await ws.send_text(html_fragment)
            except Exception:
                disconnected.add(ws)
        self._clients -= disconnected
```

### Route Handlers

**`GET /viewer`** — Returns the self-contained HTML page from `viewer_page.py`. The page includes:
- CSS for the feed layout, entity cards, tables, dark/light mode
- JS for WebSocket connection (auto-reconnect), fragment appending, auto-scroll, collapse/expand

**`WebSocket /viewer/ws`** — Accepts connections, registers with the manager, keeps alive until disconnect. Incoming messages from the browser are ignored (the viewer is write-only from server to browser).

### Dynamic Route Mounting

`start_viewer()` appends `Route("/viewer", ...)` and `WebSocketRoute("/viewer/ws", ...)` to the Starlette app's route list. `stop_viewer()` removes them. This avoids having the routes present when the viewer is inactive.

## Rendering Pipeline (`viewer_render.py`)

When a tool executes and the viewer is active, `_log_tool_call()` calls the rendering pipeline:

```
tool_name + tool_output + registry
  → detect result type
  → select renderer
  → render HTML fragment
  → wrap in feed item envelope (header + timestamp + collapse toggle)
  → broadcast via WebSocket
```

### Result Type Detection

| Tool | Result Type | Renderer |
|---|---|---|
| `query` | Query table | `render_query_table()` |
| `explore_entity` | Entity card (type-specific) | `render_entity_card()` dispatches by URI namespace |
| `search_entities` | Search results | `render_search_results()` |
| `find_links` | Cross-reference list | `render_cross_references()` |
| `get_provenance` | Provenance detail | `render_provenance()` |
| `discover_datasets` | Dataset list | `render_dataset_list()` |
| `get_schema` | Schema overview | `render_schema()` |
| `validate_sparql` | Validation result | `render_validation()` |
| Other | Generic text | `render_generic()` |

### Entity Cards

Entity-type-specific cards for `explore_entity` results. The entity type is determined by the URI namespace (using `registry.dataset_for_uri()`):

**Person card** (DPRR persons, Nomisma persons, EDH persons):
- Name (large), dates, dataset badge
- Offices held (list)
- Family/filiation
- Cross-dataset links (if any)

**Place card** (Pleiades places):
- Name, period, dataset badge
- Description
- Coordinates (if available)
- Alternate names

**Coin type card** (CRRO/OCRE types):
- Denomination, date, dataset badge
- Issuing authority
- Mint
- Obverse/reverse description

**Generic entity card** (fallback for unrecognized types):
- URI, label, dataset badge
- Property list (key-value pairs)

### Query Result Table

Styled HTML table replacing the markdown table from `toons.dumps()`. Features:
- Column headers with dataset badge
- Zebra-striped rows
- Row count footer
- URIs rendered as styled links
- Truncation for long values with expand-on-click

### Cross-Reference List

For `find_links` output. Grouped by confidence level:
- **Confirmed** — green badge
- **Probable** — amber badge
- **Candidate** — gray badge

Each link shows: source → target, relationship type, basis text.

### Feed Item Envelope

Every rendered fragment is wrapped in a feed item:

```html
<div class="feed-item" data-tool="query" data-timestamp="...">
  <div class="feed-header">
    <span class="tool-badge">query</span>
    <span class="dataset-badge">dprr</span>
    <span class="timestamp">14:32:05</span>
    <button class="collapse-toggle">collapse</button>
  </div>
  <div class="feed-body">
    <!-- rendered fragment here -->
  </div>
</div>
```

Older items (all except the newest) get the `.collapsed` class which reduces them to header-only. Click the header to expand.

## Viewer Page (`viewer_page.py`)

A single Python string constant containing the full HTML document. No external dependencies.

### CSS

- Feed layout: vertical stack, full-width items, scrollable
- Entity cards: bordered containers with header (name + badge) and body (property grid)
- Tables: full-width, fixed header, zebra rows
- Dark/light mode via `prefers-color-scheme` media query
- Dataset badges: colored by dataset (DPRR blue, Pleiades green, Nomisma gold, etc.)
- Responsive: works at any width, single column

### JavaScript

- **WebSocket client**: connects to `ws://${location.host}/viewer/ws`, auto-reconnects with exponential backoff (1s, 2s, 4s, max 30s)
- **Fragment handler**: on message, creates a `div`, sets `innerHTML` to the fragment, appends to the feed container, auto-scrolls to bottom
- **Auto-collapse**: when a new item arrives, add `.collapsed` to all previous items
- **Collapse toggle**: click header to toggle `.collapsed` class on the feed item body
- **Connection indicator**: shows connected/disconnected status in a fixed header bar

### Empty State

When no results have been pushed yet, the page shows a centered message: "Waiting for results... Run a query in Claude to see results here."

## Integration with `_log_tool_call()`

The existing `_log_tool_call()` function in `server.py` is the hook point. After appending to `app.session_log`, it checks `app.viewer`:

```python
if app.viewer is not None:
    fragment = render_tool_result(tool_name, result, app.registry)
    await app.viewer.broadcast(fragment)
```

`render_tool_result()` is the top-level dispatcher in `viewer_render.py` that selects the appropriate renderer based on tool name and result shape.

### Async Considerations

`_log_tool_call()` is currently synchronous. The WebSocket broadcast is async. Two options:
- Make `_log_tool_call()` async (preferred — it's called from async tool handlers)
- Use `asyncio.create_task()` to fire-and-forget the broadcast

The broadcast should never block tool execution. If a WebSocket send fails, the client is silently removed from the set.

## What This Does NOT Include

- **No interactive elements.** The viewer is read-only. No clickable buttons, no form inputs, no user events sent back to the server. This keeps the scope tight.
- **No persistence.** The feed is in-memory. Refreshing the browser clears it. The session log in `AppContext` is the authoritative record.
- **No maps.** Place cards show coordinates as text, not rendered on a map. Map rendering could be added later with a lightweight library (Leaflet) but is out of scope.
- **No images.** Coin type cards describe iconography as text. Linking to external numismatic image databases could be added later.
- **No export from the viewer.** Use the existing `export_report` tool for that. The viewer is for live observation, not document generation.
