# React Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inline HTML viewer with a React SPA that receives structured JSON over WebSocket and renders interactive components with entity URI popovers.

**Architecture:** Server sends typed JSON messages over WebSocket instead of HTML fragments. A new REST endpoint serves entity data for popovers. A Vite-built React app at `packages/linked-past-viewer/` is served as static files by the Python server. TanStack Query caches entity data, shadcn/ui provides accessible components.

**Tech Stack:** React 19, Vite, TypeScript, TanStack Router, TanStack Query, shadcn/ui, Tailwind CSS, react-markdown

**Spec:** `docs/superpowers/specs/2026-03-31-react-viewer-design.md`

---

## File Map

### Server-side (Python)

| Action | Path | Purpose |
|--------|------|---------|
| Modify | `packages/linked-past/linked_past/core/viewer.py` | Add history buffer + replay; rename `html_fragment` param to `message` |
| Create | `packages/linked-past/linked_past/core/viewer_api.py` | Entity REST endpoint handler |
| Modify | `packages/linked-past/linked_past/core/server.py` | JSON protocol, entity route, static file serving |
| Delete | `packages/linked-past/linked_past/core/viewer_render.py` | Replaced by React components |
| Delete | `packages/linked-past/linked_past/core/viewer_page.py` | Replaced by React app |
| Modify | `packages/linked-past/tests/test_viewer.py` | Add history tests |
| Delete | `packages/linked-past/tests/test_viewer_render.py` | Tests for deleted module |
| Create | `packages/linked-past/tests/test_viewer_api.py` | Tests for entity endpoint |

### Client-side (React)

| Action | Path | Purpose |
|--------|------|---------|
| Create | `packages/linked-past-viewer/` | New package: Vite + React SPA |

See Task 4 for the full file list within the viewer package.

---

### Task 1: Server — History buffer in ViewerManager

Add message history to ViewerManager so new clients receive all prior messages.

**Files:**
- Modify: `packages/linked-past/linked_past/core/viewer.py`
- Modify: `packages/linked-past/tests/test_viewer.py`

- [ ] **Step 1: Add history buffer to ViewerManager**

In `viewer.py`, make these changes:

Add `self._history: list[str] = []` to `__init__`.

Add a `history` property:
```python
@property
def history(self) -> list[str]:
    """All messages broadcast since activation."""
    return list(self._history)
```

In `broadcast()`, add `self._history.append(message)` as the first line (before sending to clients). Also rename the parameter from `html_fragment` to `message` and update the docstring.

In `connect()`, replay history after `accept()` and before adding to `_clients`:
```python
async def connect(self, ws: WebSocket) -> None:
    await ws.accept()
    for msg in self._history:
        await ws.send_text(msg)
    self._clients.add(ws)
```

In `deactivate()`, add `self._history.clear()` before clearing clients.

- [ ] **Step 2: Add history tests**

Append to `packages/linked-past/tests/test_viewer.py`:

```python
@pytest.mark.asyncio
async def test_broadcast_stores_history(manager):
    manager.activate()
    await manager.broadcast("msg1")
    await manager.broadcast("msg2")
    assert len(manager.history) == 2
    assert manager.history[0] == "msg1"
    assert manager.history[1] == "msg2"


@pytest.mark.asyncio
async def test_deactivate_clears_history(manager):
    manager.activate()
    await manager.broadcast("test")
    assert len(manager.history) == 1
    await manager.deactivate()
    assert len(manager.history) == 0
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest packages/linked-past/tests/test_viewer.py -v`
Expected: All 6 tests PASS

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past/linked_past/core/viewer.py packages/linked-past/tests/test_viewer.py
git commit -m "feat: add history buffer to ViewerManager — replay on new connections"
```

---

### Task 2: Server — JSON protocol + entity REST endpoint

Change `_push_to_viewer` to send JSON, update all 6 call sites, create the entity REST endpoint, delete the old HTML renderers.

**Files:**
- Modify: `packages/linked-past/linked_past/core/server.py`
- Create: `packages/linked-past/linked_past/core/viewer_api.py`
- Create: `packages/linked-past/tests/test_viewer_api.py`
- Delete: `packages/linked-past/linked_past/core/viewer_render.py`
- Delete: `packages/linked-past/linked_past/core/viewer_page.py`
- Delete: `packages/linked-past/tests/test_viewer_render.py`

- [ ] **Step 1: Write entity API handler**

Create `packages/linked-past/linked_past/core/viewer_api.py`:

```python
"""REST endpoint for entity lookups — used by the viewer's EntityPopover component."""

from __future__ import annotations

import json
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from linked_past.core.viewer import get_manager

logger = logging.getLogger(__name__)

# Predicates commonly used as display names
_NAME_PREDICATES = (
    "hasPersonName", "label", "prefLabel", "skos:prefLabel",
    "rdfs:label", "title", "name", "foaf:name",
)


def _extract_name(uri: str, properties: list[dict[str, str]]) -> str:
    """Extract a display name from entity properties, falling back to URI fragment."""
    for pred in _NAME_PREDICATES:
        for prop in properties:
            pred_local = prop["pred"].rsplit("/", 1)[-1].rsplit("#", 1)[-1]
            if pred_local == pred:
                return prop["obj"]
    return uri.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1]


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

    # Access registry and linkage from the app state stored on the manager
    registry = mgr.app_context.registry
    linkage = mgr.app_context.linkage

    ds_name = registry.dataset_for_uri(uri)
    properties: list[dict[str, str]] = []

    if ds_name:
        try:
            store = registry.get_store(ds_name)
            from linked_past.core.store import execute_query

            rows = execute_query(store, f"SELECT ?pred ?obj WHERE {{ <{uri}> ?pred ?obj . }} LIMIT 50")
            properties = [{"pred": r["pred"], "obj": r["obj"] or ""} for r in rows]
        except Exception as e:
            logger.warning("Entity query failed for %s: %s", uri, e)

    # Cross-references
    xrefs = []
    if linkage:
        from linked_past.core.server import _find_store_xrefs

        linkage_links = linkage.find_links(uri)
        store_links = _find_store_xrefs(uri, registry)
        seen = set()
        for link in linkage_links + store_links:
            if link["target"] not in seen:
                seen.add(link["target"])
                xrefs.append(link)

    name = _extract_name(uri, properties)

    return JSONResponse({
        "uri": uri,
        "name": name,
        "dataset": ds_name,
        "properties": properties,
        "xrefs": xrefs,
    })
```

- [ ] **Step 2: Add `app_context` to ViewerManager**

In `viewer.py`, add `app_context` parameter to `__init__` and store it:

```python
def __init__(self, app_context=None) -> None:
    self._clients: set[WebSocket] = set()
    self._active: bool = False
    self._history: list[str] = []
    self.app_context = app_context
```

Update `server.py` line ~486 where the manager is created:
```python
viewer_manager = ViewerManager(app_context=_shared_ctx)
```

- [ ] **Step 3: Write entity API tests**

Create `packages/linked-past/tests/test_viewer_api.py`:

```python
"""Tests for the entity REST endpoint."""

from linked_past.core.viewer_api import _extract_name


def test_extract_name_from_label():
    props = [{"pred": "http://www.w3.org/2000/01/rdf-schema#label", "obj": "Roma"}]
    assert _extract_name("https://pleiades.stoa.org/places/423025", props) == "Roma"


def test_extract_name_from_person_name():
    props = [
        {"pred": "http://romanrepublic.ac.uk/rdf/ontology#hasPersonName", "obj": "Gaius Julius Caesar"},
        {"pred": "http://romanrepublic.ac.uk/rdf/ontology#hasNomen", "obj": "Julius"},
    ]
    assert _extract_name("http://romanrepublic.ac.uk/rdf/entity/Person/1957", props) == "Gaius Julius Caesar"


def test_extract_name_fallback_to_uri():
    props = [{"pred": "http://example.org/somePred", "obj": "some value"}]
    assert _extract_name("http://example.org/things/Widget42", props) == "Widget42"
```

- [ ] **Step 4: Run entity API tests**

Run: `uv run pytest packages/linked-past/tests/test_viewer_api.py -v`
Expected: All 3 PASS

- [ ] **Step 5: Replace `_push_to_viewer` with JSON protocol**

In `server.py`, replace the `_push_to_viewer` function (line ~317):

```python
async def _push_to_viewer(app: AppContext, tool_name: str, dataset: str | None, data: dict):
    """Push a typed JSON message to the viewer if active."""
    if app.viewer is None or not app.viewer.is_active:
        return
    import json
    from datetime import datetime, timezone

    message = json.dumps({
        "type": tool_name,
        "dataset": dataset,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    })
    logger.info("Viewer push: tool=%s dataset=%s clients=%d", tool_name, dataset, app.viewer.client_count)
    await app.viewer.broadcast(message)
```

- [ ] **Step 6: Update `query` tool push (line ~615)**

Replace the existing `if app.viewer and app.viewer.is_active:` block with:

```python
        if app.viewer and app.viewer.is_active:
            await _push_to_viewer(app, "query", dataset, {
                "rows": result.rows,
                "columns": list(result.rows[0].keys()) if result.rows else [],
                "sparql": result.sparql,
                "row_count": len(result.rows),
            })
```

- [ ] **Step 7: Update `search_entities` push (two sites)**

Replace the early-return empty case (line ~704):
```python
        if app.viewer and app.viewer.is_active:
            await _push_to_viewer(app, "search", dataset, {
                "query_text": query_text,
                "results": [],
            })
```

Replace the normal-path push (line ~752):
```python
        if app.viewer and app.viewer.is_active:
            await _push_to_viewer(app, "search", dataset, {
                "query_text": query_text,
                "results": all_results,
            })
```

- [ ] **Step 8: Update `explore_entity` push (line ~836)**

Replace:
```python
        if app.viewer and app.viewer.is_active:
            name = uri.rsplit("/", 1)[-1]
            for pred in ("hasPersonName", "label", "prefLabel", "rdfs:label", "title", "name"):
                for row in rows:
                    if row["pred"].rsplit("/", 1)[-1].rsplit("#", 1)[-1] == pred:
                        name = row["obj"]
                        break
                if name != uri.rsplit("/", 1)[-1]:
                    break
            await _push_to_viewer(app, "entity", ds_name, {
                "uri": uri,
                "name": name,
                "properties": [{"pred": r["pred"], "obj": r["obj"] or ""} for r in rows],
                "xrefs": xrefs,
            })
```

- [ ] **Step 9: Update `find_links` push (line ~892)**

Replace:
```python
        if app.viewer and app.viewer.is_active:
            await _push_to_viewer(app, "links", ds_name, {
                "uri": uri,
                "links": [
                    {"target": l["target"], "relationship": l.get("relationship", ""),
                     "confidence": l.get("confidence", ""), "basis": l.get("basis", "")}
                    for l in linkage_links + store_links
                ],
            })
```

- [ ] **Step 10: Update `push_to_viewer` tool (line ~1360)**

Replace:
```python
    @mcp.tool()
    async def push_to_viewer(ctx: Context, content: str, title: str | None = None) -> str:
        """Push markdown content to the browser viewer as a styled report."""
        app: AppContext = ctx.request_context.lifespan_context

        if app.viewer is None or not app.viewer.is_active:
            return "Viewer is not running. Call start_viewer() first."

        await _push_to_viewer(app, "report", None, {
            "title": title,
            "markdown": content,
        })
        return f"Pushed to viewer{f': {title}' if title else ''}."
```

- [ ] **Step 11: Register entity API route + static file serving**

In `server.py`, in the route registration block (line ~481), add the entity API route and change the viewer page handler to serve static files:

```python
    from starlette.routing import Route, WebSocketRoute
    from linked_past.core.viewer import ViewerManager, set_manager, viewer_ws_handler
    from linked_past.core.viewer_api import entity_handler

    viewer_manager = ViewerManager(app_context=_shared_ctx)
    set_manager(viewer_manager)
    _shared_ctx.viewer = viewer_manager

    # Find React app dist directory
    _viewer_dist = Path(__file__).resolve().parent.parent.parent.parent / "linked-past-viewer" / "dist"

    async def _viewer_page(request):
        """Serve the React app's index.html, or error if not built."""
        from starlette.responses import HTMLResponse, PlainTextResponse

        index = _viewer_dist / "index.html"
        if not index.exists():
            return PlainTextResponse(
                "Viewer not built. Run: cd packages/linked-past-viewer && npm install && npm run build",
                status_code=404,
            )
        return HTMLResponse(index.read_text())

    async def _viewer_static(request):
        """Serve static assets from the React app's dist directory."""
        from starlette.responses import FileResponse, PlainTextResponse

        path = request.path_params.get("path", "")
        file_path = (_viewer_dist / path).resolve()
        if not str(file_path).startswith(str(_viewer_dist.resolve())):
            return PlainTextResponse("Forbidden", status_code=403)
        if not file_path.exists() or not file_path.is_file():
            # SPA fallback — return index.html for unmatched routes
            index = _viewer_dist / "index.html"
            if index.exists():
                from starlette.responses import HTMLResponse
                return HTMLResponse(index.read_text())
            return PlainTextResponse("Not found", status_code=404)
        return FileResponse(file_path)

    mcp._custom_starlette_routes.extend([
        Route("/viewer", _viewer_page, methods=["GET"]),
        Route("/viewer/{path:path}", _viewer_static, methods=["GET"]),
        Route("/viewer/api/entity", entity_handler, methods=["GET"]),
        WebSocketRoute("/viewer/ws", viewer_ws_handler),
    ])
```

**Important:** The `/viewer/api/entity` route must come BEFORE `/viewer/{path:path}` in the list, otherwise the catch-all will match it. Reorder:

```python
    mcp._custom_starlette_routes.extend([
        Route("/viewer/api/entity", entity_handler, methods=["GET"]),
        WebSocketRoute("/viewer/ws", viewer_ws_handler),
        Route("/viewer", _viewer_page, methods=["GET"]),
        Route("/viewer/{path:path}", _viewer_static, methods=["GET"]),
    ])
```

- [ ] **Step 12: Clean up `viewer.py` — remove stale imports and `viewer_page_handler`**

In `packages/linked-past/linked_past/core/viewer.py`:
- Remove the import: `from linked_past.core.viewer_page import VIEWER_HTML`
- Remove the `viewer_page_handler` function entirely (the React app replaces it)
- Update the `broadcast()` docstring from "HTML fragment" to "message"

- [ ] **Step 13: Delete old HTML renderer files**

```bash
git rm packages/linked-past/linked_past/core/viewer_render.py
git rm packages/linked-past/linked_past/core/viewer_page.py
git rm packages/linked-past/tests/test_viewer_render.py
```

- [ ] **Step 13: Run lint and tests**

```bash
uv run ruff check packages/linked-past/
uv run pytest packages/linked-past/tests/test_viewer.py packages/linked-past/tests/test_viewer_api.py -v
```

Expected: All tests PASS, lint clean.

- [ ] **Step 14: Commit**

```bash
git add -A
git commit -m "feat: JSON WebSocket protocol, entity REST endpoint, static file serving"
```

---

### Task 3: Scaffold React app

Create the `packages/linked-past-viewer/` package with Vite, React, TypeScript, Tailwind, and shadcn/ui.

**Files:**
- Create: `packages/linked-past-viewer/` (full scaffold)

- [ ] **Step 1: Initialize the package**

```bash
mkdir -p packages/linked-past-viewer
cd packages/linked-past-viewer
npm init -y
```

Then edit `package.json` to add scripts:
```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview"
  }
}
```

- [ ] **Step 2: Install dependencies**

```bash
npm install react react-dom @tanstack/react-router @tanstack/react-query react-markdown
npm install -D vite @vitejs/plugin-react typescript @types/react @types/react-dom tailwindcss @tailwindcss/vite @tailwindcss/typography
```

- [ ] **Step 3: Write `vite.config.ts`**

```typescript
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/viewer/",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/viewer/ws": {
        target: "http://localhost:8000",
        ws: true,
      },
      "/viewer/api": {
        target: "http://localhost:8000",
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
```

- [ ] **Step 4: Write `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
```

- [ ] **Step 5: Write `index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>linked-past viewer</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/viewer/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Write `src/app.css`** (Tailwind entry)

```css
@import "tailwindcss";
```

- [ ] **Step 7: Initialize shadcn/ui**

```bash
npx shadcn@latest init -d
npx shadcn@latest add popover table card badge collapsible
```

If shadcn prompts for config, accept defaults (New York style, CSS variables, `src/components/ui/`).

- [ ] **Step 8: Write `src/main.tsx`**

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRouter, RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./app.css";
import { routeTree } from "./route-tree";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: Infinity, // Entity data doesn't change during a session
    },
  },
});

const router = createRouter({ routeTree, basepath: "/viewer" });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
```

- [ ] **Step 9: Write `src/route-tree.tsx`**

```tsx
import {
  createRootRoute,
  createRoute,
  Outlet,
} from "@tanstack/react-router";
import { ViewerLayout } from "./components/viewer-layout";

const rootRoute = createRootRoute({
  component: () => <Outlet />,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: ViewerLayout,
});

export const routeTree = rootRoute.addChildren([indexRoute]);
```

- [ ] **Step 10: Write placeholder `src/components/viewer-layout.tsx`**

```tsx
export function ViewerLayout() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur px-4 h-10 flex items-center text-sm">
        <span className="font-semibold">linked-past viewer</span>
      </header>
      <main className="max-w-4xl mx-auto p-4">
        <p className="text-muted-foreground text-center py-20">
          Waiting for results… Run a query in Claude to see results here.
        </p>
      </main>
    </div>
  );
}
```

- [ ] **Step 11: Build and verify**

```bash
npm run build
ls dist/
```

Expected: `dist/index.html` and `dist/assets/` with JS/CSS bundles.

- [ ] **Step 12: Add to .gitignore**

Add to `packages/linked-past-viewer/.gitignore`:
```
node_modules/
dist/
```

- [ ] **Step 13: Commit**

```bash
cd /path/to/repo/root
git add packages/linked-past-viewer/
git commit -m "feat: scaffold React viewer — Vite + TanStack Router/Query + shadcn/ui + Tailwind"
```

---

### Task 4: Types + WebSocket hook + URI utilities

The foundation that all components depend on.

**Files:**
- Create: `packages/linked-past-viewer/src/lib/types.ts`
- Create: `packages/linked-past-viewer/src/lib/uri.ts`
- Create: `packages/linked-past-viewer/src/hooks/use-viewer-socket.ts`

- [ ] **Step 1: Write `src/lib/types.ts`**

```typescript
export type QueryData = {
  rows: Record<string, string>[];
  columns: string[];
  sparql: string;
  row_count: number;
};

export type EntityData = {
  uri: string;
  name: string;
  dataset: string | null;
  properties: { pred: string; obj: string }[];
  xrefs: XrefLink[];
};

export type XrefLink = {
  target: string;
  relationship: string;
  confidence: string;
  basis: string;
};

export type LinksData = {
  uri: string;
  links: XrefLink[];
};

export type SearchData = {
  query_text: string;
  results: { uri: string; label: string; dataset: string }[];
};

export type ReportData = {
  title: string | null;
  markdown: string;
};

export type ViewerMessage =
  | { type: "query"; dataset: string | null; timestamp: string; data: QueryData }
  | { type: "entity"; dataset: string | null; timestamp: string; data: EntityData }
  | { type: "links"; dataset: string | null; timestamp: string; data: LinksData }
  | { type: "search"; dataset: string | null; timestamp: string; data: SearchData }
  | { type: "report"; dataset: string | null; timestamp: string; data: ReportData };
```

- [ ] **Step 2: Write `src/lib/uri.ts`**

```typescript
const URI_NAMESPACES: Record<string, string> = {
  "http://romanrepublic.ac.uk/rdf/": "dprr",
  "https://pleiades.stoa.org/places/": "pleiades",
  "http://n2t.net/ark:/99152/": "periodo",
  "http://nomisma.org/id/": "nomisma",
  "http://numismatics.org/crro/id/": "crro",
  "http://numismatics.org/ocre/id/": "ocre",
  "http://edh-www.adw.uni-heidelberg.de/edh/": "edh",
  "https://edh-www.adw.uni-heidelberg.de/edh/": "edh",
};

export function datasetForUri(uri: string): string | null {
  for (const [ns, ds] of Object.entries(URI_NAMESPACES)) {
    if (uri.startsWith(ns)) return ds;
  }
  return null;
}

export function shortUri(uri: string): string {
  return uri.split("/").pop()?.split("#").pop() ?? uri;
}
```

- [ ] **Step 3: Write `src/hooks/use-viewer-socket.ts`**

```typescript
import { useCallback, useEffect, useRef, useState } from "react";
import type { ViewerMessage } from "../lib/types";

export function useViewerSocket() {
  const [messages, setMessages] = useState<ViewerMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);

  const connect = useCallback(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/viewer/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      backoffRef.current = 1000;
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as ViewerMessage;
        setMessages((prev) => [...prev, msg]);
      } catch {
        console.warn("Failed to parse viewer message:", e.data);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      wsRef.current = null;
      const delay = Math.min(backoffRef.current, 30000);
      backoffRef.current *= 2;
      setTimeout(connect, delay);
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return { messages, isConnected };
}
```

- [ ] **Step 4: Build to verify no type errors**

```bash
cd packages/linked-past-viewer
npx tsc --noEmit
npm run build
```

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-viewer/src/lib/ packages/linked-past-viewer/src/hooks/
git commit -m "feat: add types, URI utilities, and WebSocket hook"
```

---

### Task 5: Core components — Feed, FeedItem, DatasetBadge, ConnectionStatus

**Files:**
- Create: `packages/linked-past-viewer/src/components/dataset-badge.tsx`
- Create: `packages/linked-past-viewer/src/components/connection-status.tsx`
- Create: `packages/linked-past-viewer/src/components/feed-item.tsx`
- Create: `packages/linked-past-viewer/src/components/feed.tsx`
- Modify: `packages/linked-past-viewer/src/components/viewer-layout.tsx`

- [ ] **Step 1: Write `dataset-badge.tsx`**

```tsx
const COLORS: Record<string, string> = {
  dprr: "bg-blue-500",
  pleiades: "bg-green-500",
  periodo: "bg-purple-500",
  nomisma: "bg-yellow-500 text-black",
  crro: "bg-orange-500",
  ocre: "bg-red-500",
  edh: "bg-cyan-500",
};

export function DatasetBadge({ dataset }: { dataset: string }) {
  const color = COLORS[dataset] ?? "bg-gray-500";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold text-white ${color}`}>
      {dataset}
    </span>
  );
}
```

- [ ] **Step 2: Write `connection-status.tsx`**

```tsx
export function ConnectionStatus({ connected }: { connected: boolean }) {
  return (
    <span className="flex items-center gap-1.5 text-xs">
      <span
        className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`}
      />
      {connected ? "connected" : "disconnected"}
    </span>
  );
}
```

- [ ] **Step 3: Write `feed-item.tsx`**

```tsx
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useState } from "react";
import type { ViewerMessage } from "../lib/types";
import { DatasetBadge } from "./dataset-badge";

export function FeedItem({
  message,
  defaultOpen = true,
  children,
}: {
  message: ViewerMessage;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const time = new Date(message.timestamp).toLocaleTimeString();

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="border rounded-lg mb-3 overflow-hidden">
      <CollapsibleTrigger className="flex items-center gap-2 w-full px-3 py-2 bg-muted/50 hover:bg-muted text-sm cursor-pointer select-none">
        <span className="bg-primary text-primary-foreground px-2 py-0.5 rounded text-[11px] font-semibold uppercase">
          {message.type}
        </span>
        {message.dataset && <DatasetBadge dataset={message.dataset} />}
        <span className="ml-auto text-muted-foreground tabular-nums text-xs">{time}</span>
        <span className="text-muted-foreground text-[11px]">{open ? "collapse" : "expand"}</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="p-3">
        {children}
      </CollapsibleContent>
    </Collapsible>
  );
}
```

- [ ] **Step 4: Write `feed.tsx`**

```tsx
import { useEffect, useRef } from "react";
import type { ViewerMessage } from "../lib/types";
import { EntityCard } from "./entity-card";
import { FeedItem } from "./feed-item";
import { MarkdownReport } from "./markdown-report";
import { QueryResult } from "./query-result";
import { SearchResults } from "./search-results";
import { XrefList } from "./xref-list";

function MessageBody({ message }: { message: ViewerMessage }) {
  switch (message.type) {
    case "query":
      return <QueryResult data={message.data} />;
    case "entity":
      return <EntityCard data={message.data} />;
    case "links":
      return <XrefList links={message.data.links} />;
    case "search":
      return <SearchResults data={message.data} />;
    case "report":
      return <MarkdownReport data={message.data} />;
  }
}

export function Feed({ messages }: { messages: ViewerMessage[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  if (messages.length === 0) {
    return (
      <p className="text-muted-foreground text-center py-20">
        Waiting for results… Run a query in Claude to see results here.
      </p>
    );
  }

  return (
    <div>
      {messages.map((msg, i) => (
        <FeedItem
          key={`${msg.timestamp}-${i}`}
          message={msg}
          defaultOpen={i === messages.length - 1}
        >
          <MessageBody message={msg} />
        </FeedItem>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
```

- [ ] **Step 5: Update `viewer-layout.tsx`**

```tsx
import { useViewerSocket } from "../hooks/use-viewer-socket";
import { ConnectionStatus } from "./connection-status";
import { Feed } from "./feed";

export function ViewerLayout() {
  const { messages, isConnected } = useViewerSocket();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur px-4 h-10 flex items-center text-sm">
        <span className="font-semibold">linked-past viewer</span>
        <span className="ml-auto">
          <ConnectionStatus connected={isConnected} />
        </span>
      </header>
      <main className="max-w-4xl mx-auto p-4">
        <Feed messages={messages} />
      </main>
    </div>
  );
}
```

- [ ] **Step 6: Create stub components** (filled in Task 6)

Create minimal stubs so the build doesn't break:

`src/components/query-result.tsx`:
```tsx
import type { QueryData } from "../lib/types";
export function QueryResult({ data }: { data: QueryData }) {
  return <pre className="text-xs">{JSON.stringify(data, null, 2)}</pre>;
}
```

`src/components/entity-card.tsx`:
```tsx
import type { EntityData } from "../lib/types";
export function EntityCard({ data }: { data: EntityData }) {
  return <pre className="text-xs">{JSON.stringify(data, null, 2)}</pre>;
}
```

`src/components/xref-list.tsx`:
```tsx
import type { XrefLink } from "../lib/types";
export function XrefList({ links }: { links: XrefLink[] }) {
  return <pre className="text-xs">{JSON.stringify(links, null, 2)}</pre>;
}
```

`src/components/search-results.tsx`:
```tsx
import type { SearchData } from "../lib/types";
export function SearchResults({ data }: { data: SearchData }) {
  return <pre className="text-xs">{JSON.stringify(data, null, 2)}</pre>;
}
```

`src/components/markdown-report.tsx`:
```tsx
import type { ReportData } from "../lib/types";
export function MarkdownReport({ data }: { data: ReportData }) {
  return <pre className="text-xs">{data.markdown}</pre>;
}
```

- [ ] **Step 7: Build and verify**

```bash
cd packages/linked-past-viewer
npx tsc --noEmit
npm run build
```

- [ ] **Step 8: Commit**

```bash
git add packages/linked-past-viewer/src/components/
git commit -m "feat: add Feed, FeedItem, DatasetBadge, ConnectionStatus + stubs"
```

---

### Task 6: Result components — QueryResult, EntityCard, XrefList, SearchResults, MarkdownReport

Replace the stubs with real implementations.

**Files:**
- Modify: All 5 stub components from Task 5

- [ ] **Step 1: Write `query-result.tsx`**

```tsx
import type { QueryData } from "../lib/types";
import { EntityUri } from "./entity-uri";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function isUri(value: string): boolean {
  return value.startsWith("http://") || value.startsWith("https://");
}

export function QueryResult({ data }: { data: QueryData }) {
  return (
    <div>
      {data.sparql && (
        <details className="mb-2">
          <summary className="text-xs text-muted-foreground font-semibold cursor-pointer">
            SPARQL
          </summary>
          <pre className="mt-1 p-2 rounded bg-muted text-xs overflow-x-auto whitespace-pre-wrap">
            {data.sparql}
          </pre>
        </details>
      )}
      {data.rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No results</p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                {data.columns.map((col) => (
                  <TableHead key={col}>{col}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.rows.map((row, i) => (
                <TableRow key={i}>
                  {data.columns.map((col) => (
                    <TableCell key={col} className="max-w-[300px] truncate">
                      {isUri(row[col] ?? "") ? (
                        <EntityUri uri={row[col]} />
                      ) : (
                        row[col]
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p className="text-xs text-muted-foreground mt-1">
            {data.row_count} row{data.row_count !== 1 ? "s" : ""}
          </p>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Write `entity-card.tsx`**

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { EntityData } from "../lib/types";
import { DatasetBadge } from "./dataset-badge";
import { EntityUri } from "./entity-uri";
import { XrefList } from "./xref-list";

export function EntityCard({ data }: { data: EntityData }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        {data.dataset && <DatasetBadge dataset={data.dataset} />}
        <CardTitle className="text-lg">{data.name}</CardTitle>
        <p className="text-xs text-muted-foreground font-mono">{data.uri}</p>
      </CardHeader>
      <CardContent>
        {data.properties.length > 0 && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm mb-3">
            {data.properties.map((p, i) => {
              const pred = p.pred.split("/").pop()?.split("#").pop() ?? p.pred;
              return (
                <div key={i} className="contents">
                  <dt className="font-semibold text-muted-foreground">{pred}</dt>
                  <dd className="break-words">
                    {p.obj.startsWith("http") ? <EntityUri uri={p.obj} /> : p.obj}
                  </dd>
                </div>
              );
            })}
          </dl>
        )}
        {data.xrefs.length > 0 && (
          <div className="pt-2 border-t">
            <h4 className="text-xs font-semibold text-muted-foreground mb-1">Cross-references</h4>
            <XrefList links={data.xrefs} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: Write `xref-list.tsx`**

```tsx
import { Badge } from "@/components/ui/badge";
import type { XrefLink } from "../lib/types";
import { EntityUri } from "./entity-uri";

const CONFIDENCE_COLORS: Record<string, string> = {
  confirmed: "bg-green-500 hover:bg-green-500",
  probable: "bg-yellow-500 hover:bg-yellow-500 text-black",
  candidate: "bg-gray-400 hover:bg-gray-400",
  concordance: "bg-blue-400 hover:bg-blue-400",
  "in-data": "bg-cyan-400 hover:bg-cyan-400",
};

export function XrefList({ links }: { links: XrefLink[] }) {
  if (links.length === 0) {
    return <p className="text-sm text-muted-foreground">No cross-references found.</p>;
  }

  // Group by confidence
  const groups = new Map<string, XrefLink[]>();
  for (const link of links) {
    const conf = link.confidence || "unknown";
    if (!groups.has(conf)) groups.set(conf, []);
    groups.get(conf)!.push(link);
  }

  return (
    <div className="space-y-3">
      {["confirmed", "probable", "candidate", "concordance", "in-data", "unknown"].map((conf) => {
        const items = groups.get(conf);
        if (!items) return null;
        const color = CONFIDENCE_COLORS[conf] ?? "bg-gray-400 hover:bg-gray-400";
        return (
          <div key={conf}>
            <Badge className={`text-[10px] mb-1 ${color}`}>{conf}</Badge>
            <div className="space-y-1 pl-2 border-l-2">
              {items.map((link, i) => (
                <div key={i} className="text-sm">
                  <span className="text-muted-foreground">{link.relationship}</span>
                  {" → "}
                  <EntityUri uri={link.target} />
                  {link.basis && (
                    <span className="block text-xs text-muted-foreground">{link.basis}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Write `search-results.tsx`**

```tsx
import type { SearchData } from "../lib/types";
import { DatasetBadge } from "./dataset-badge";
import { EntityUri } from "./entity-uri";

export function SearchResults({ data }: { data: SearchData }) {
  if (data.results.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No entities found matching &ldquo;{data.query_text}&rdquo;.
      </p>
    );
  }

  // Group by dataset
  const groups = new Map<string, typeof data.results>();
  for (const r of data.results) {
    if (!groups.has(r.dataset)) groups.set(r.dataset, []);
    groups.get(r.dataset)!.push(r);
  }

  return (
    <div className="space-y-3">
      <p className="text-sm">
        Results for &ldquo;{data.query_text}&rdquo;
      </p>
      {[...groups.entries()].map(([ds, results]) => (
        <div key={ds}>
          <DatasetBadge dataset={ds} />
          <div className="mt-1 space-y-1">
            {results.map((r, i) => (
              <div key={i} className="text-sm">
                <span className="font-medium">{r.label}</span>
                <EntityUri uri={r.uri} />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Write `markdown-report.tsx`**

```tsx
import Markdown from "react-markdown";
import type { ReportData } from "../lib/types";

export function MarkdownReport({ data }: { data: ReportData }) {
  return (
    <div>
      {data.title && <h2 className="text-lg font-semibold mb-2">{data.title}</h2>}
      <div className="prose prose-sm dark:prose-invert max-w-none">
        <Markdown
          components={{
            table: ({ children }) => (
              <table className="w-full border-collapse text-sm">{children}</table>
            ),
            th: ({ children }) => (
              <th className="text-left p-1.5 border-b-2 font-semibold bg-muted/50">{children}</th>
            ),
            td: ({ children }) => (
              <td className="p-1.5 border-b">{children}</td>
            ),
          }}
        >
          {data.markdown}
        </Markdown>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Create stub `entity-uri.tsx`** (filled in Task 7)

```tsx
import { datasetForUri, shortUri } from "../lib/uri";
import { DatasetBadge } from "./dataset-badge";

export function EntityUri({ uri }: { uri: string }) {
  const dataset = datasetForUri(uri);
  return (
    <span className="inline-flex items-center gap-1">
      <code className="text-xs text-primary underline">{shortUri(uri)}</code>
      {dataset && <DatasetBadge dataset={dataset} />}
    </span>
  );
}
```

- [ ] **Step 7: Build and verify**

```bash
cd packages/linked-past-viewer
npx tsc --noEmit
npm run build
```

- [ ] **Step 8: Commit**

```bash
git add packages/linked-past-viewer/src/components/
git commit -m "feat: add QueryResult, EntityCard, XrefList, SearchResults, MarkdownReport"
```

---

### Task 7: EntityUri popover with TanStack Query

The interactive URI component with hover popover that fetches entity data.

**Files:**
- Create: `packages/linked-past-viewer/src/hooks/use-entity-query.ts`
- Create: `packages/linked-past-viewer/src/components/entity-popover.tsx`
- Modify: `packages/linked-past-viewer/src/components/entity-uri.tsx`

- [ ] **Step 1: Write `use-entity-query.ts`**

```typescript
import { useQuery } from "@tanstack/react-query";
import type { EntityData } from "../lib/types";

async function fetchEntity(uri: string): Promise<EntityData> {
  const res = await fetch(`/viewer/api/entity?uri=${encodeURIComponent(uri)}`);
  if (!res.ok) throw new Error(`Entity fetch failed: ${res.status}`);
  return res.json();
}

export function useEntityQuery(uri: string, enabled: boolean) {
  return useQuery({
    queryKey: ["entity", uri],
    queryFn: () => fetchEntity(uri),
    enabled,
    staleTime: Infinity,
  });
}
```

- [ ] **Step 2: Write `entity-popover.tsx`**

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { EntityData } from "../lib/types";
import { DatasetBadge } from "./dataset-badge";

export function EntityPopoverContent({ data }: { data: EntityData }) {
  // Show top ~5 properties
  const topProps = data.properties.slice(0, 5);
  return (
    <Card className="border-0 shadow-none w-[320px]">
      <CardHeader className="p-3 pb-1">
        <div className="flex items-center gap-1.5">
          {data.dataset && <DatasetBadge dataset={data.dataset} />}
          <span className="text-xs text-muted-foreground font-mono truncate">
            {data.uri.split("/").pop()}
          </span>
        </div>
        <CardTitle className="text-base">{data.name}</CardTitle>
      </CardHeader>
      <CardContent className="p-3 pt-0">
        {topProps.length > 0 && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-xs">
            {topProps.map((p, i) => {
              const pred = p.pred.split("/").pop()?.split("#").pop() ?? p.pred;
              return (
                <div key={i} className="contents">
                  <dt className="font-semibold text-muted-foreground">{pred}</dt>
                  <dd className="truncate">{p.obj}</dd>
                </div>
              );
            })}
          </dl>
        )}
        {data.xrefs.length > 0 && (
          <div className="mt-2 pt-2 border-t text-xs text-muted-foreground">
            {data.xrefs.length} cross-reference{data.xrefs.length !== 1 ? "s" : ""}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: Update `entity-uri.tsx` with popover**

```tsx
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useState } from "react";
import { useEntityQuery } from "../hooks/use-entity-query";
import { datasetForUri, shortUri } from "../lib/uri";
import { DatasetBadge } from "./dataset-badge";
import { EntityPopoverContent } from "./entity-popover";

export function EntityUri({ uri }: { uri: string }) {
  const dataset = datasetForUri(uri);
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useEntityQuery(uri, open);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className="inline-flex items-center gap-1 cursor-pointer"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        <code className="text-xs text-primary underline">{shortUri(uri)}</code>
        {dataset && <DatasetBadge dataset={dataset} />}
      </PopoverTrigger>
      <PopoverContent
        className="p-0 w-auto"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        side="bottom"
        align="start"
        sideOffset={2}
      >
        {isLoading ? (
          <div className="p-4 text-sm text-muted-foreground">Loading…</div>
        ) : data ? (
          <EntityPopoverContent data={data} />
        ) : (
          <div className="p-4 text-sm text-muted-foreground">{uri}</div>
        )}
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 4: Build and verify**

```bash
cd packages/linked-past-viewer
npx tsc --noEmit
npm run build
```

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-viewer/src/
git commit -m "feat: add EntityUri popover with TanStack Query fetch + cache"
```

---

### Task 8: Build, integrate, and verify end-to-end

Build the React app, verify the Python server serves it, test the full flow.

**Files:**
- Modify: `packages/linked-past-viewer/package.json` (add build script if missing)

- [ ] **Step 1: Build the React app**

```bash
cd packages/linked-past-viewer
npm run build
ls dist/index.html dist/assets/
```

Expected: `index.html` and JS/CSS bundles in `assets/`.

- [ ] **Step 2: Run Python lint and tests**

```bash
uv run ruff check .
uv run pytest -q
```

Expected: All pass.

- [ ] **Step 3: Manual end-to-end test**

1. Start the MCP server: `uv run linked-past-server`
2. Open http://localhost:8000/viewer — should show the React app with "Waiting for results..."
3. WebSocket should connect (green indicator)
4. Call `start_viewer()` via MCP client
5. Run a query — should appear in the feed as a styled table
6. Hover a URI in the table — popover should show entity data
7. Call `push_to_viewer(content="# Test\n\nHello **world**")` — should render markdown

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: end-to-end integration fixes for React viewer"
```

- [ ] **Step 5: Final commit with build artifacts excluded**

Verify `packages/linked-past-viewer/.gitignore` excludes `dist/` and `node_modules/`.

```bash
git status
git add -A
git commit -m "feat: React viewer complete — JSON protocol, entity popovers, feed layout"
```
