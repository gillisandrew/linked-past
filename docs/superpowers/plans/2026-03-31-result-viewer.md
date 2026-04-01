# Result Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a browser-based live results viewer to the MCP server — a scrollable feed of styled query tables, entity cards, and cross-reference lists, pushed over WebSocket as tools execute.

**Architecture:** `start_viewer` tool mounts `/viewer` (HTML page) and `/viewer/ws` (WebSocket) on the existing Starlette app. Tool functions push structured data to a `ViewerManager` which renders entity-type-aware HTML fragments and broadcasts them to connected browsers. `stop_viewer` tears it down.

**Tech Stack:** Python 3.13, Starlette (WebSocket + Route), asyncio, HTML/CSS/JS (inline, no build step)

**Spec:** `docs/superpowers/specs/2026-03-31-result-viewer-design.md`

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `packages/linked-past/linked_past/core/viewer_page.py` | HTML/CSS/JS page as a Python string constant |
| Create | `packages/linked-past/linked_past/core/viewer_render.py` | HTML fragment renderers for each result type |
| Create | `packages/linked-past/linked_past/core/viewer.py` | ViewerManager, route handlers, mount/unmount |
| Create | `packages/linked-past/tests/test_viewer_render.py` | Tests for HTML renderers |
| Create | `packages/linked-past/tests/test_viewer.py` | Tests for ViewerManager |
| Modify | `packages/linked-past/linked_past/core/server.py` | Add viewer field to AppContext, start/stop tools, push hooks in tool functions |

---

### Task 1: Create the viewer page (`viewer_page.py`)

The self-contained HTML/CSS/JS served at `/viewer`. No tests needed — this is a static asset.

**Files:**
- Create: `packages/linked-past/linked_past/core/viewer_page.py`

- [ ] **Step 1: Write `viewer_page.py`**

```python
"""Self-contained HTML page for the result viewer.

Served at /viewer. Connects to /viewer/ws via WebSocket.
Incoming messages are HTML fragments appended to the feed.
"""

VIEWER_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>linked-past viewer</title>
<style>
  :root {
    --bg: #ffffff; --bg-alt: #f5f5f5; --fg: #1a1a1a; --fg-muted: #666;
    --border: #e0e0e0; --accent: #2563eb;
    --badge-dprr: #3b82f6; --badge-pleiades: #22c55e; --badge-periodo: #a855f7;
    --badge-nomisma: #eab308; --badge-crro: #f97316; --badge-ocre: #ef4444;
    --badge-edh: #06b6d4; --badge-default: #6b7280;
    --confirmed: #22c55e; --probable: #eab308; --candidate: #9ca3af;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0f0f0f; --bg-alt: #1a1a1a; --fg: #e5e5e5; --fg-muted: #999;
      --border: #333; --accent: #60a5fa;
    }
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
         background: var(--bg); color: var(--fg); }
  #header { position: fixed; top: 0; left: 0; right: 0; height: 40px; background: var(--bg-alt);
            border-bottom: 1px solid var(--border); display: flex; align-items: center;
            padding: 0 16px; z-index: 100; font-size: 13px; }
  #header .title { font-weight: 600; }
  #header .status { margin-left: auto; }
  #header .status.connected { color: var(--confirmed); }
  #header .status.disconnected { color: var(--badge-ocre); }
  #feed { padding: 52px 16px 16px; max-width: 900px; margin: 0 auto; }
  #empty { text-align: center; color: var(--fg-muted); padding: 80px 20px; font-size: 15px; }
  .feed-item { border: 1px solid var(--border); border-radius: 8px; margin-bottom: 12px;
               overflow: hidden; background: var(--bg); }
  .feed-header { display: flex; align-items: center; gap: 8px; padding: 8px 12px;
                 background: var(--bg-alt); border-bottom: 1px solid var(--border);
                 cursor: pointer; font-size: 12px; user-select: none; }
  .feed-header:hover { background: var(--border); }
  .feed-body { padding: 12px; }
  .feed-item.collapsed .feed-body { display: none; }
  .feed-item.collapsed .feed-header { border-bottom: none; }
  .tool-badge { background: var(--accent); color: white; padding: 2px 8px; border-radius: 4px;
                font-size: 11px; font-weight: 600; text-transform: uppercase; }
  .dataset-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;
                   color: white; }
  .dataset-badge[data-ds="dprr"] { background: var(--badge-dprr); }
  .dataset-badge[data-ds="pleiades"] { background: var(--badge-pleiades); }
  .dataset-badge[data-ds="periodo"] { background: var(--badge-periodo); }
  .dataset-badge[data-ds="nomisma"] { background: var(--badge-nomisma); }
  .dataset-badge[data-ds="crro"] { background: var(--badge-crro); }
  .dataset-badge[data-ds="ocre"] { background: var(--badge-ocre); }
  .dataset-badge[data-ds="edh"] { background: var(--badge-edh); }
  .timestamp { color: var(--fg-muted); margin-left: auto; font-variant-numeric: tabular-nums; }
  /* Entity cards */
  .entity-card { }
  .entity-card h3 { font-size: 18px; margin-bottom: 8px; }
  .entity-card .subtitle { color: var(--fg-muted); font-size: 13px; margin-bottom: 12px; }
  .entity-card .props { display: grid; grid-template-columns: auto 1fr; gap: 4px 12px;
                        font-size: 13px; }
  .entity-card .props dt { font-weight: 600; color: var(--fg-muted); }
  .entity-card .props dd { }
  .entity-card .xrefs { margin-top: 12px; font-size: 13px; }
  .entity-card .xrefs li { margin-bottom: 4px; }
  /* Query table */
  .query-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .query-table th { text-align: left; padding: 6px 8px; background: var(--bg-alt);
                    border-bottom: 2px solid var(--border); font-weight: 600; }
  .query-table td { padding: 6px 8px; border-bottom: 1px solid var(--border);
                    max-width: 300px; overflow: hidden; text-overflow: ellipsis;
                    white-space: nowrap; }
  .query-table tr:hover td { background: var(--bg-alt); }
  .query-table .footer { color: var(--fg-muted); font-size: 12px; padding: 8px 0; }
  /* Cross-references */
  .xref-group { margin-bottom: 12px; }
  .xref-group h4 { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
  .confidence-badge { display: inline-block; padding: 1px 6px; border-radius: 3px;
                      font-size: 11px; font-weight: 600; color: white; }
  .confidence-badge.confirmed { background: var(--confirmed); }
  .confidence-badge.probable { background: var(--probable); color: #1a1a1a; }
  .confidence-badge.candidate { background: var(--candidate); }
  .xref-item { font-size: 13px; margin-bottom: 6px; padding-left: 8px;
               border-left: 3px solid var(--border); }
  /* Search results */
  .search-group { margin-bottom: 12px; }
  .search-group h4 { font-size: 14px; margin-bottom: 4px; }
  .search-item { font-size: 13px; padding: 4px 0; }
  .search-item .uri { color: var(--fg-muted); font-size: 11px; }
  /* Generic */
  .generic-result { white-space: pre-wrap; font-family: 'SF Mono', Menlo, monospace;
                    font-size: 12px; line-height: 1.5; }
</style>
</head>
<body>
<div id="header">
  <span class="title">linked-past viewer</span>
  <span id="status" class="status disconnected">disconnected</span>
</div>
<div id="feed">
  <div id="empty">Waiting for results&hellip;<br>Run a query in Claude to see results here.</div>
</div>
<script>
(function() {
  const feed = document.getElementById('feed');
  const empty = document.getElementById('empty');
  const status = document.getElementById('status');
  let ws = null;
  let backoff = 1000;

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(proto + '//' + location.host + '/viewer/ws');
    ws.onopen = () => {
      status.textContent = 'connected';
      status.className = 'status connected';
      backoff = 1000;
    };
    ws.onclose = () => {
      status.textContent = 'disconnected';
      status.className = 'status disconnected';
      setTimeout(connect, Math.min(backoff, 30000));
      backoff *= 2;
    };
    ws.onmessage = (e) => {
      if (empty) empty.remove();
      // Collapse all existing items
      feed.querySelectorAll('.feed-item:not(.collapsed)').forEach(el => el.classList.add('collapsed'));
      // Append new fragment
      const div = document.createElement('div');
      div.innerHTML = e.data;
      while (div.firstChild) feed.appendChild(div.firstChild);
      // Auto-scroll
      window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    };
  }

  // Toggle collapse on header click
  feed.addEventListener('click', (e) => {
    const header = e.target.closest('.feed-header');
    if (header) header.parentElement.classList.toggle('collapsed');
  });

  connect();
})();
</script>
</body>
</html>
"""
```

- [ ] **Step 2: Commit**

```bash
git add packages/linked-past/linked_past/core/viewer_page.py
git commit -m "feat: add viewer page — self-contained HTML/CSS/JS for result feed"
```

---

### Task 2: Create HTML fragment renderers (`viewer_render.py`)

Renders structured tool data into HTML fragments. Each renderer is a pure function: data in, HTML string out.

**Files:**
- Create: `packages/linked-past/linked_past/core/viewer_render.py`
- Create: `packages/linked-past/tests/test_viewer_render.py`

- [ ] **Step 1: Write failing tests**

```python
# packages/linked-past/tests/test_viewer_render.py
"""Tests for viewer HTML fragment renderers."""

from linked_past.core.viewer_render import (
    render_entity_card,
    render_feed_item,
    render_generic,
    render_query_table,
    render_xref_list,
)


def test_render_query_table_basic():
    rows = [{"name": "Caesar", "office": "consul"}, {"name": "Pompey", "office": "consul"}]
    html = render_query_table(rows, dataset="dprr")
    assert "<table" in html
    assert "Caesar" in html
    assert "Pompey" in html
    assert "<th" in html  # column headers


def test_render_query_table_empty():
    html = render_query_table([], dataset="dprr")
    assert "No results" in html


def test_render_entity_card_person():
    properties = [
        {"pred": "hasPersonName", "obj": "Gaius Julius Caesar"},
        {"pred": "hasEraFrom", "obj": "-100"},
        {"pred": "hasHighestOffice", "obj": "dictator"},
    ]
    html = render_entity_card(
        uri="http://romanrepublic.ac.uk/rdf/entity/Person/1957",
        properties=properties,
        dataset="dprr",
        xrefs=[],
    )
    assert "entity-card" in html
    assert "Gaius Julius Caesar" in html
    assert "dprr" in html


def test_render_entity_card_with_xrefs():
    properties = [{"pred": "label", "obj": "Roma"}]
    xrefs = [
        {"target": "http://nomisma.org/id/rome", "relationship": "skos:closeMatch",
         "confidence": "confirmed", "basis": "Wikidata concordance"},
    ]
    html = render_entity_card(
        uri="https://pleiades.stoa.org/places/423025",
        properties=properties,
        dataset="pleiades",
        xrefs=xrefs,
    )
    assert "Roma" in html
    assert "nomisma.org" in html
    assert "confirmed" in html


def test_render_xref_list():
    links = [
        {"target": "http://nomisma.org/id/pompey", "relationship": "skos:closeMatch",
         "confidence": "confirmed", "basis": "Manual alignment"},
        {"target": "http://example.org/candidate", "relationship": "owl:sameAs",
         "confidence": "candidate", "basis": "Automated match"},
    ]
    html = render_xref_list(links)
    assert "confirmed" in html
    assert "candidate" in html
    assert "nomisma.org" in html


def test_render_generic():
    html = render_generic("Some plain text output from a tool")
    assert "generic-result" in html
    assert "Some plain text output" in html


def test_render_generic_escapes_html():
    html = render_generic("<script>alert('xss')</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_feed_item():
    html = render_feed_item(
        tool_name="query",
        dataset="dprr",
        body_html="<p>test</p>",
    )
    assert "feed-item" in html
    assert "feed-header" in html
    assert "query" in html
    assert 'data-ds="dprr"' in html
    assert "<p>test</p>" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_viewer_render.py -v`
Expected: FAIL — `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Write implementation**

```python
# packages/linked-past/linked_past/core/viewer_render.py
"""HTML fragment renderers for the result viewer.

Each renderer takes structured data and returns an HTML string.
Fragments are wrapped in feed_item() before being broadcast.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape


def render_query_table(rows: list[dict[str, str]], dataset: str) -> str:
    """Render SPARQL query results as a styled HTML table."""
    if not rows:
        return '<p class="generic-result">No results returned.</p>'

    cols = list(rows[0].keys())
    header = "".join(f"<th>{escape(c)}</th>" for c in cols)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{escape(str(row.get(c, '')))}</td>" for c in cols)
        body_rows.append(f"<tr>{cells}</tr>")

    return (
        f'<table class="query-table">'
        f"<thead><tr>{header}</tr></thead>"
        f'<tbody>{"".join(body_rows)}</tbody>'
        f"</table>"
        f'<div class="query-table footer">{len(rows)} result{"s" if len(rows) != 1 else ""}</div>'
    )


def render_entity_card(
    uri: str,
    properties: list[dict[str, str]],
    dataset: str,
    xrefs: list[dict] | None = None,
) -> str:
    """Render an entity as a styled card with properties and cross-references."""
    # Try to find a display name from common predicates
    name = uri.rsplit("/", 1)[-1]
    name_preds = {"hasPersonName", "label", "rdfs:label", "prefLabel", "title", "name"}
    for prop in properties:
        pred_local = prop["pred"].rsplit("/", 1)[-1].rsplit("#", 1)[-1]
        if pred_local in name_preds:
            name = prop["obj"]
            break

    props_html = ""
    for prop in properties:
        pred_local = prop["pred"].rsplit("/", 1)[-1].rsplit("#", 1)[-1]
        obj_val = escape(str(prop["obj"]))
        if len(obj_val) > 120:
            obj_val = obj_val[:120] + "..."
        props_html += f"<dt>{escape(pred_local)}</dt><dd>{obj_val}</dd>"

    xrefs_html = ""
    if xrefs:
        xrefs_html = '<div class="xrefs"><strong>Cross-references:</strong><ul>'
        for link in xrefs:
            conf = link.get("confidence", "")
            badge = f'<span class="confidence-badge {escape(conf)}">{escape(conf)}</span>' if conf else ""
            xrefs_html += (
                f"<li>{badge} {escape(link.get('relationship', ''))} "
                f"&rarr; <code>{escape(link['target'])}</code></li>"
            )
        xrefs_html += "</ul></div>"

    return (
        f'<div class="entity-card">'
        f"<h3>{escape(name)}</h3>"
        f'<div class="subtitle"><code>{escape(uri)}</code></div>'
        f'<dl class="props">{props_html}</dl>'
        f"{xrefs_html}"
        f"</div>"
    )


def render_xref_list(links: list[dict]) -> str:
    """Render cross-reference links grouped by confidence."""
    if not links:
        return '<p class="generic-result">No cross-references found.</p>'

    groups: dict[str, list[dict]] = {}
    for link in links:
        conf = link.get("confidence", "unknown")
        groups.setdefault(conf, []).append(link)

    parts = []
    for conf in ["confirmed", "probable", "candidate", "unknown"]:
        if conf not in groups:
            continue
        badge = f'<span class="confidence-badge {escape(conf)}">{escape(conf)}</span>'
        items = ""
        for link in groups[conf]:
            rel = escape(link.get("relationship", ""))
            target = escape(link["target"])
            basis = escape(link.get("basis", ""))
            items += (
                f'<div class="xref-item">'
                f"<strong>{rel}</strong> &rarr; <code>{target}</code>"
                f'<br><span style="color:var(--fg-muted)">{basis}</span>'
                f"</div>"
            )
        parts.append(f'<div class="xref-group"><h4>{badge}</h4>{items}</div>')

    return "".join(parts)


def render_generic(text: str) -> str:
    """Render plain text as a preformatted block."""
    return f'<div class="generic-result">{escape(text)}</div>'


def render_feed_item(tool_name: str, dataset: str | None, body_html: str) -> str:
    """Wrap a rendered fragment in a feed item envelope with header."""
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    ds_badge = ""
    if dataset:
        ds_badge = f'<span class="dataset-badge" data-ds="{escape(dataset)}">{escape(dataset)}</span>'
    return (
        f'<div class="feed-item">'
        f'<div class="feed-header">'
        f'<span class="tool-badge">{escape(tool_name)}</span>'
        f"{ds_badge}"
        f'<span class="timestamp">{ts}</span>'
        f"</div>"
        f'<div class="feed-body">{body_html}</div>'
        f"</div>"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_viewer_render.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Run lint**

Run: `uv run ruff check packages/linked-past/linked_past/core/viewer_render.py`
Expected: All checks passed

- [ ] **Step 6: Commit**

```bash
git add packages/linked-past/linked_past/core/viewer_render.py packages/linked-past/tests/test_viewer_render.py
git commit -m "feat: add viewer HTML renderers — entity cards, query tables, cross-references"
```

---

### Task 3: Create the ViewerManager (`viewer.py`)

WebSocket manager, route handlers, and dynamic route mounting.

**Files:**
- Create: `packages/linked-past/linked_past/core/viewer.py`
- Create: `packages/linked-past/tests/test_viewer.py`

- [ ] **Step 1: Write failing tests**

```python
# packages/linked-past/tests/test_viewer.py
"""Tests for ViewerManager."""

import asyncio

import pytest

from linked_past.core.viewer import ViewerManager


@pytest.fixture
def manager():
    return ViewerManager()


def test_manager_starts_inactive(manager):
    assert not manager.is_active
    assert manager.client_count == 0


def test_manager_activate_deactivate(manager):
    manager.activate()
    assert manager.is_active
    manager.deactivate()
    assert not manager.is_active


@pytest.mark.asyncio
async def test_broadcast_no_clients(manager):
    """Broadcast with no clients should not raise."""
    manager.activate()
    await manager.broadcast("<p>test</p>")


def test_viewer_url(manager):
    assert manager.viewer_url("localhost", 8000) == "http://localhost:8000/viewer"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/linked-past/tests/test_viewer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# packages/linked-past/linked_past/core/viewer.py
"""Viewer lifecycle: WebSocket manager, route handlers, dynamic route mounting."""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from linked_past.core.viewer_page import VIEWER_HTML

logger = logging.getLogger(__name__)


class ViewerManager:
    """Manages WebSocket connections and broadcasts HTML fragments to browsers."""

    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def activate(self):
        self._active = True

    def deactivate(self):
        self._active = False
        self._clients.clear()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.add(ws)
        logger.info("Viewer client connected (%d total)", len(self._clients))

    async def disconnect(self, ws: WebSocket):
        self._clients.discard(ws)
        logger.info("Viewer client disconnected (%d remaining)", len(self._clients))

    async def broadcast(self, html_fragment: str):
        """Send an HTML fragment to all connected browsers."""
        if not self._clients:
            return
        disconnected = set()
        for ws in self._clients:
            try:
                await ws.send_text(html_fragment)
            except Exception:
                disconnected.add(ws)
        self._clients -= disconnected

    def viewer_url(self, host: str, port: int) -> str:
        return f"http://{host}:{port}/viewer"


async def _viewer_page(request: Request) -> HTMLResponse:
    """Serve the viewer HTML page."""
    return HTMLResponse(VIEWER_HTML)


async def _viewer_ws(websocket: WebSocket):
    """Handle a viewer WebSocket connection."""
    manager: ViewerManager = websocket.app.state.viewer_manager
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; ignore incoming messages (viewer is write-only)
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


def mount_viewer(app, manager: ViewerManager) -> None:
    """Add /viewer and /viewer/ws routes to the Starlette app."""
    app.state.viewer_manager = manager
    app.routes.append(Route("/viewer", _viewer_page, methods=["GET"]))
    app.routes.append(WebSocketRoute("/viewer/ws", _viewer_ws))
    manager.activate()
    logger.info("Viewer mounted at /viewer")


def unmount_viewer(app, manager: ViewerManager) -> None:
    """Remove viewer routes from the Starlette app."""
    app.routes[:] = [
        r for r in app.routes
        if not (hasattr(r, "path") and r.path in ("/viewer", "/viewer/ws"))
    ]
    manager.deactivate()
    logger.info("Viewer unmounted")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/linked-past/tests/test_viewer.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Run lint**

Run: `uv run ruff check packages/linked-past/linked_past/core/viewer.py`

- [ ] **Step 6: Commit**

```bash
git add packages/linked-past/linked_past/core/viewer.py packages/linked-past/tests/test_viewer.py
git commit -m "feat: add ViewerManager — WebSocket manager with route mount/unmount"
```

---

### Task 4: Integrate viewer into server.py

Add the `viewer` field to `AppContext`, the `start_viewer`/`stop_viewer` tools, and push hooks in tool functions.

**Files:**
- Modify: `packages/linked-past/linked_past/core/server.py`

This is the largest task. The changes are:

1. Add `viewer` field to `AppContext`
2. Add a `_push_to_viewer()` helper
3. Add `start_viewer` and `stop_viewer` tools
4. Add viewer push calls after `_log_tool_call` in `query`, `explore_entity`, `search_entities`, `find_links`

- [ ] **Step 1: Add `viewer` field to `AppContext`**

In `server.py`, change the `AppContext` dataclass (around line 36-46):

```python
@dataclass
class AppContext:
    registry: DatasetRegistry
    linkage: LinkageGraph | None = None
    search: SearchIndex | None = None
    meta: object = None  # MetaEntityIndex
    session_log: list = None
    viewer: object = None  # ViewerManager | None

    def __post_init__(self):
        if self.session_log is None:
            self.session_log = []
```

- [ ] **Step 2: Add `_push_to_viewer()` helper**

Add after `_log_tool_call()` (around line 311):

```python
async def _push_to_viewer(app: AppContext, tool_name: str, dataset: str | None, body_html: str):
    """Push an HTML fragment to the viewer if active."""
    if app.viewer is None or not app.viewer.is_active:
        return
    from linked_past.core.viewer_render import render_feed_item

    fragment = render_feed_item(tool_name, dataset, body_html)
    await app.viewer.broadcast(fragment)
```

- [ ] **Step 3: Add `start_viewer` and `stop_viewer` tools**

Add inside `create_mcp_server()`, after the existing tool definitions (before the `return mcp` line):

```python
    @mcp.tool()
    async def start_viewer(ctx: Context) -> str:
        """Start the browser-based result viewer. Opens a live feed of query results, entity cards, and cross-references at a URL you can open in your browser."""
        app: AppContext = ctx.request_context.lifespan_context

        if app.viewer is not None and app.viewer.is_active:
            host = mcp.settings.host or "localhost"
            port = mcp.settings.port or 8000
            url = app.viewer.viewer_url("localhost", port)
            return f"Viewer already running at {url}"

        from linked_past.core.viewer import ViewerManager, mount_viewer

        manager = ViewerManager()
        # Get the ASGI app from the server internals
        starlette_app = ctx.request_context.session._app
        mount_viewer(starlette_app, manager)
        app.viewer = manager

        port = mcp.settings.port or 8000
        url = manager.viewer_url("localhost", port)
        return f"Viewer started at {url}"

    @mcp.tool()
    async def stop_viewer(ctx: Context) -> str:
        """Stop the browser-based result viewer."""
        app: AppContext = ctx.request_context.lifespan_context

        if app.viewer is None or not app.viewer.is_active:
            return "Viewer is not running."

        from linked_past.core.viewer import unmount_viewer

        starlette_app = ctx.request_context.session._app
        unmount_viewer(starlette_app, app.viewer)
        app.viewer = None
        return "Viewer stopped."
```

- [ ] **Step 4: Add viewer push to `query` tool**

In the `query` tool function, after the `_log_tool_call` line (around line 586), add:

```python
        # Push to viewer
        if app.viewer and app.viewer.is_active:
            from linked_past.core.viewer_render import render_query_table

            table_html = render_query_table(result.rows, dataset)
            await _push_to_viewer(app, "query", dataset, table_html)
```

- [ ] **Step 5: Add viewer push to `explore_entity` tool**

In the `explore_entity` tool function, after the `_log_tool_call` line (around line 793), add:

```python
        # Push to viewer
        if app.viewer and app.viewer.is_active:
            from linked_past.core.viewer_render import render_entity_card

            # rows may be undefined if the SPARQL query in the try block failed
            entity_props = rows if "rows" in dir() and rows else []
            card_html = render_entity_card(uri, entity_props, ds_name or "unknown", xrefs)
            await _push_to_viewer(app, "explore_entity", ds_name, card_html)
```

Note: `rows` is the list of `{"pred": ..., "obj": ...}` dicts from the SPARQL query at line 748 (inside a try block — may be undefined on error). `xrefs` is built at line 768 and is always defined.

- [ ] **Step 6: Add viewer push to `find_links` tool**

In the `find_links` tool function, after the `_log_tool_call` line (around line 844), add:

```python
        # Push to viewer
        if app.viewer and app.viewer.is_active:
            from linked_past.core.viewer_render import render_xref_list

            xref_html = render_xref_list(linkage_links + store_links)
            await _push_to_viewer(app, "find_links", ds_name, xref_html)
```

Note: `linkage_links`, `store_links`, and `ds_name` are already in scope.

- [ ] **Step 7: Add viewer push to `search_entities` tool**

In the `search_entities` tool function, after the `_log_tool_call` calls (there are two — at lines 670 and 713), add the same pattern:

```python
        # Push to viewer
        if app.viewer and app.viewer.is_active:
            from linked_past.core.viewer_render import render_generic

            await _push_to_viewer(app, "search_entities", dataset, render_generic(output))
```

Search results use `render_generic` for now — the structured data isn't easily accessible at the point where `_log_tool_call` is called (it's already been joined into markdown). A dedicated search renderer can be added later.

- [ ] **Step 8: Add generic viewer push as fallback in `_log_tool_call`**

For all other tools that don't have explicit viewer pushes, add a generic fallback. Modify `_log_tool_call()` to accept the app's viewer:

At the end of `_log_tool_call()`, after `app.session_log.append(entry)`:

```python
    # Async viewer push happens in tool functions for structured data.
    # This is only for tools that don't have explicit viewer integration.
```

Actually, no — the explicit pushes in each tool function are sufficient. Tools without viewer pushes simply don't appear in the viewer, which is fine for `validate_sparql`, `get_schema`, `discover_datasets`, `get_provenance`, and `update_dataset`. These are informational tools where the text output Claude shows is sufficient.

- [ ] **Step 9: Run lint**

Run: `uv run ruff check packages/linked-past/linked_past/core/server.py`

- [ ] **Step 10: Run full test suite**

Run: `uv run pytest -q --ignore=packages/linked-past/tests/test_embeddings.py --ignore=packages/linked-past/tests/test_embeddings_multi.py`
Expected: All tests pass (existing + new viewer tests)

- [ ] **Step 11: Commit**

```bash
git add packages/linked-past/linked_past/core/server.py
git commit -m "feat: integrate viewer — start/stop tools and push hooks for query, entity, links"
```

---

### Task 5: Run full test suite and lint

Final verification that everything works together.

**Files:** None (verification only)

- [ ] **Step 1: Run lint**

Run: `uv run ruff check .`
Expected: All checks passed

- [ ] **Step 2: Run tests**

Run: `uv run pytest -q`
Expected: All tests pass (no new failures)

- [ ] **Step 3: Commit any fixups if needed**

```bash
git add -A
git commit -m "fix: test/lint fixups for result viewer"
```
