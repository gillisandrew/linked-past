# React Viewer Design

Replace the inline HTML viewer with a React SPA that receives structured JSON over WebSocket and renders interactive components — entity URI popovers, styled query tables, entity cards, and markdown reports.

## Architecture

```
packages/linked-past-viewer/        ← new Vite + React SPA
├── src/
│   ├── components/                 ← FeedItem, QueryResult, EntityCard, XrefList,
│   │                                 SearchResults, MarkdownReport, EntityUri, EntityPopover
│   ├── components/ui/              ← shadcn/ui (Popover, Table, Card, Badge, Collapsible)
│   ├── hooks/                      ← useViewerSocket, useEntityQuery
│   ├── lib/                        ← types, message parsing, WebSocket client
│   ├── routes/                     ← TanStack Router (single route: index)
│   └── main.tsx
├── dist/                           ← build output (gitignored)
├── package.json
├── vite.config.ts
├── tailwind.config.ts
└── tsconfig.json

Server changes (packages/linked-past/):
├── core/viewer.py                  ← broadcast JSON; history buffer; replay on connect
├── core/viewer_render.py           ← deleted
├── core/viewer_page.py             ← deleted
├── core/viewer_api.py              ← new: GET /viewer/api/entity REST endpoint
└── core/server.py                  ← _push_to_viewer sends dicts; /viewer serves dist/
```

### Data Flow

1. Tool executes → `_push_to_viewer` builds a typed dict → `json.dumps` → broadcast over WebSocket
2. React app receives JSON → `useViewerSocket` hook parses message → appends to feed state
3. Feed component renders the appropriate component based on `message.type`
4. User hovers an entity URI → `useEntityQuery` (TanStack Query) fetches `GET /viewer/api/entity?uri=...`
5. Popover renders EntityCard with cached data; subsequent hovers are instant
6. New WebSocket connections receive full message history → feed populates immediately

### Build & Serve

```bash
cd packages/linked-past-viewer
npm install
npm run build          # produces dist/
```

The Python server serves the built files:
- `GET /viewer` → `dist/index.html`
- `GET /viewer/assets/*` → `dist/assets/*` (JS/CSS bundles)
- `WebSocket /viewer/ws` → structured JSON messages
- `GET /viewer/api/entity?uri=...` → entity data JSON

If `dist/` doesn't exist (viewer not built), `/viewer` returns a plain text error with build instructions.

## WebSocket Protocol

Every message is a JSON object with `type`, `dataset`, `timestamp`, and `data` fields.

### Message Types

```typescript
type BaseMessage = {
  type: string
  dataset: string | null
  timestamp: string  // ISO 8601
}

type QueryMessage = BaseMessage & {
  type: "query"
  data: {
    rows: Record<string, string>[]
    columns: string[]
    sparql: string
    row_count: number
  }
}

type EntityMessage = BaseMessage & {
  type: "entity"
  data: {
    uri: string
    name: string
    properties: { pred: string; obj: string }[]
    xrefs: { target: string; relationship: string; confidence: string; basis: string }[]
  }
}

type LinksMessage = BaseMessage & {
  type: "links"
  data: {
    uri: string
    links: { target: string; relationship: string; confidence: string; basis: string }[]
  }
}

type SearchMessage = BaseMessage & {
  type: "search"
  data: {
    query_text: string
    results: { uri: string; label: string; dataset: string }[]
  }
}

type ReportMessage = BaseMessage & {
  type: "report"
  data: {
    title: string | null
    markdown: string
  }
}

type ViewerMessage = QueryMessage | EntityMessage | LinksMessage | SearchMessage | ReportMessage
```

### History Replay

The `ViewerManager` keeps a buffer of all broadcast messages. On new WebSocket connection, the server replays the full history before adding the client to the live broadcast set. This means:
- Browser refresh restores the full feed
- Opening additional browser tabs shows the same state
- History clears when `stop_viewer()` is called

## React Components

### Component Tree

```
App (TanStack Router + Query providers)
└── ViewerLayout (header + scrollable feed)
    ├── ConnectionStatus (WebSocket indicator)
    ├── Feed (scrollable list, auto-scroll on new items)
    │   ├── FeedItem (collapsible wrapper — shadcn Collapsible)
    │   │   header: tool badge + dataset badge + timestamp
    │   │   body: one of:
    │   │     ├── QueryResult (shadcn Table + SPARQL details)
    │   │     │   └── EntityUri (in table cells containing URIs)
    │   │     ├── EntityCard (shadcn Card — name, props grid, xrefs)
    │   │     │   └── EntityUri (in xref targets)
    │   │     ├── XrefList (grouped by confidence — shadcn Badge)
    │   │     │   └── EntityUri (target URIs)
    │   │     ├── SearchResults (grouped by dataset)
    │   │     │   └── EntityUri (result URIs)
    │   │     └── MarkdownReport (react-markdown with custom table component)
    │   └── EmptyState ("Waiting for results...")
    └── EntityPopover (shadcn Popover — positioned at hovered EntityUri)
```

### EntityUri Component

The key interactive component. Appears wherever URIs show up in the feed. Detects the dataset from the URI namespace and shows a colored badge.

**Idle state:** Styled as a link with dataset badge. Hover triggers popover.

**Popover (on hover):**
- TanStack Query fetches `GET /viewer/api/entity?uri=...` with `enabled: isHovered`
- Loading state: spinner in popover
- Loaded: mini EntityCard (name, top ~5 properties, xrefs if any)
- Cached: instant on repeat hover (TanStack Query `staleTime: Infinity`)
- Popover positioned via shadcn Popover (Radix + Floating UI under the hood)

### Hooks

**`useViewerSocket()`**
- Manages WebSocket connection to `/viewer/ws`
- Auto-reconnect with exponential backoff (1s → 30s)
- Parses incoming JSON messages into typed `ViewerMessage` objects
- Returns `{ messages: ViewerMessage[], isConnected: boolean }`
- History replay is transparent — messages from replay and live are identical

**`useEntityQuery(uri: string, enabled: boolean)`**
- TanStack Query wrapper around `GET /viewer/api/entity?uri=...`
- `enabled` controlled by hover state (lazy fetch)
- `staleTime: Infinity` — entity data doesn't change during a session
- Returns `{ data: EntityData, isLoading, isError }`

## Tech Stack

```bash
cd packages/linked-past-viewer
npm init -y
npm install react react-dom @tanstack/react-router @tanstack/react-query react-markdown
npm install -D vite @vitejs/plugin-react typescript @types/react @types/react-dom tailwindcss @tailwindcss/vite
npx shadcn@latest init
npx shadcn@latest add popover table card badge collapsible
```

- **Vite** — build tool, dev server with HMR
- **TanStack Router** — type-safe SPA routing (single route for now, extensible later)
- **TanStack Query** — entity popover data fetching + caching
- **shadcn/ui** — Popover, Table, Card, Badge, Collapsible (Radix + Tailwind, copied into project)
- **Tailwind CSS** — utility-first styling, dark mode via `class` strategy
- **react-markdown** — markdown report rendering with custom component overrides
- **TypeScript** — all source files

## Server-Side Changes

### `_push_to_viewer` sends JSON

```python
async def _push_to_viewer(app, tool_name, dataset, data):
    import json
    from datetime import datetime, timezone

    message = json.dumps({
        "type": tool_name,
        "dataset": dataset,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    })
    await app.viewer.broadcast(message)
```

Each tool call site passes a dict:
- `query` → `{"rows": result.rows, "columns": list(result.rows[0].keys()), "sparql": result.sparql, "row_count": len(result.rows)}`
- `explore_entity` → `{"uri": uri, "name": name, "properties": rows, "xrefs": xrefs}`
- `find_links` → `{"uri": uri, "links": linkage_links + store_links}`
- `search_entities` → `{"query_text": query_text, "results": results_list}`
- `push_to_viewer` → `{"title": title, "markdown": content}`

### ViewerManager changes

- `broadcast()` appends to `self._history` before sending
- `connect()` replays `self._history` to new client before adding to live set
- `deactivate()` clears history

### Entity REST endpoint (`viewer_api.py`)

`GET /viewer/api/entity?uri=...`

- Determines dataset from URI namespace via `registry.dataset_for_uri(uri)`
- Queries the dataset store: `SELECT ?pred ?obj WHERE { <uri> ?pred ?obj } LIMIT 50`
- Finds xrefs from linkage graph + store SKOS/OWL predicates
- Extracts display name from common predicates (hasPersonName, label, prefLabel, etc.)
- Returns JSON matching `EntityMessage.data` shape

Registered as a static Starlette route alongside `/viewer` and `/viewer/ws`.

### Static file serving

`/viewer` and `/viewer/*` serve from the React app's `dist/` directory. The server locates `dist/` by walking up from the `linked_past` package to find `packages/linked-past-viewer/dist/`. Any path not matching a static file returns `index.html` (SPA fallback).

### Files deleted

- `viewer_page.py` — replaced by React app
- `viewer_render.py` — replaced by React components
- Tests for these modules replaced with tests for JSON message format and REST endpoint

## What This Does NOT Include

- **No SSR** — pure SPA, no server rendering. The viewer is a dev tool, not a public website.
- **No graph visualization** — link graphs are a natural follow-up but out of scope for v1. The component architecture supports adding a `LinkGraph` component later.
- **No feed persistence** — history lives in memory on the ViewerManager. Server restart clears it. The session log in AppContext is the authoritative record.
- **No authentication** — localhost-only dev tool.
- **No dev server proxy** — during development, Vite's dev server proxies `/viewer/ws` and `/viewer/api/*` to the Python server. In production build, everything is served by the Python server directly.
