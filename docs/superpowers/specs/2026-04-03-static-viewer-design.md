# Static Session Viewer for GitHub Pages

**Date:** 2026-04-03
**Status:** Draft
**Package:** `packages/linked-past-viewer`

## Purpose

Deploy a pared-down version of the linked-past viewer to GitHub Pages that allows users to paste or upload a session JSONL file and browse it in the same feed interface. Primary use case: sharing session artifacts with colleagues without requiring them to run the server.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Package structure | Same package, second Vite entry point | Maximizes component reuse, single dependency tree |
| Architecture | Thin adapter + Zod boundary | ~200 lines new code, no premature abstraction |
| Landing UX | Drop zone + paste area | Paste is cheap to add and useful for small sessions |
| Entity URIs | Colored pills, click opens URI in new tab | Preserves visual identity without server dependency |
| Deployment | GitHub Actions on push to main | Keeps hosted version current automatically |
| Message validation | Zod schemas, shared by both viewers | Runtime validation + type inference, natural for TS stack |
| Format versioning | Session-level `format_version` field | Lightweight; version checked at parse boundary |

## Non-Goals (MVP)

- Entity popover fetching (on roadmap)
- Gist-based sharing via URL hash + backend proxy (on roadmap)
- IndexedDB persistence in static viewer
- Versioned/tagged deployments

## Message Format Versioning

### Session Metadata Preamble

Every exported JSONL file begins with a metadata line:

```json
{"format_version": 1, "type": "session_meta", "session_id": "20260402-143000", "created_at": "2026-04-02T14:30:00.000Z"}
```

- `ViewerManager.activate()` writes this as the first line when creating a new session file.
- Existing sessions without it are loadable; version is assumed as `1`.
- Unknown `format_version` values produce a warning, not a rejection: "This session was created with a newer format. Some items may not render correctly."

### Zod Schemas (`lib/schemas.ts`)

Single source of truth for message shapes, replacing hand-written interfaces in `types.ts`:

- `SessionMetaSchema` — the preamble line
- `QueryDataSchema`, `EntityDataSchema`, `LinksDataSchema`, `SearchDataSchema`, `ReportDataSchema` — one per message type
- `ViewerMessageSchema` — discriminated union on `type`, wrapping base fields (`session_id`, `seq`, `dataset`, `timestamp`) plus type-specific data
- Types inferred via `z.infer<>` — `types.ts` re-exports these inferred types

## JSONL Parsing (`lib/parse-session.ts`)

```typescript
parseSessionJsonl(text: string): {
  messages: ViewerMessage[];
  errors: ParseError[];
  formatVersion: number | null;
}
```

- Splits on newlines, parses each as JSON, validates against `ViewerMessageSchema`.
- First line checked for `session_meta` — extracts `format_version`.
- Invalid lines produce `ParseError` objects: `{ line: number, raw: string, error: string }`.
- Parse errors do not block loading. They are surfaced as inline items in the session feed at their sequence position, with a human-readable message (e.g., "Line 14: Unknown message type 'foo' — skipping") and the raw content truncated for inspection.
- Valid lines become `ViewerMessage[]` sorted by `seq`.

## Project Structure

```
packages/linked-past-viewer/
├── src/
│   ├── main.tsx                  # existing live viewer entry
│   ├── static.tsx                # NEW — static viewer entry
│   ├── lib/
│   │   ├── schemas.ts            # NEW — Zod schemas for all message types
│   │   ├── types.ts              # MODIFIED — inferred from Zod schemas
│   │   ├── parse-session.ts      # NEW — JSONL parser + validator
│   │   ├── store.ts              # existing, unchanged
│   │   └── uri.ts                # existing, unchanged
│   ├── components/
│   │   ├── feed.tsx              # shared, unchanged
│   │   ├── feed-item.tsx         # shared, unchanged
│   │   ├── markdown-report.tsx   # shared, unchanged
│   │   ├── mermaid-block.tsx     # shared, unchanged
│   │   ├── query-result.tsx      # shared, unchanged
│   │   ├── entity-uri.tsx        # MODIFIED — static mode: no popover fetch
│   │   ├── drop-zone.tsx         # NEW — file drop + paste landing
│   │   ├── session-picker.tsx    # REFACTORED — shadcn Select, export buttons
│   │   └── ...                   # other shared components unchanged
│   └── hooks/
│       ├── use-viewer-socket.ts  # MODIFIED — add Zod parsing at boundary
│       ├── use-entity-query.ts   # existing, unused in static mode
│       └── use-static-session.ts # NEW — parse JSONL into ViewerMessage[]
├── index.html                    # existing live viewer entry
├── static.html                   # NEW — static viewer entry
└── vite.config.ts                # MODIFIED — add static build target
```

## Static Viewer UI

### Entry Point (`static.tsx`)

Minimal React app:
- No React Query provider (no server calls)
- No TanStack Router (single page)
- Renders `StaticApp` — landing page or feed, depending on whether a session is loaded

### Landing Page (`drop-zone.tsx`)

- **File drop zone** — drag-and-drop or click-to-browse for `.jsonl` files
- **Paste area** — collapsible textarea for pasting raw JSONL content
- **Load button** — validates via `parseSessionJsonl`, transitions to feed view
- Parse errors appear inline in the feed as `FeedItem` entries with a warning style variant (amber border, warning icon, human-readable message + truncated raw line)

### Data Hook (`use-static-session.ts`)

```typescript
useStaticSession(): {
  messages: ViewerMessage[];
  errors: ParseError[];
  loadFromText: (text: string) => void;
  loadFromFile: (file: File) => void;
  clear: () => void;
  isLoaded: boolean;
}
```

Purely in-memory — no IndexedDB, no persistence.

### "Load Another" — toolbar button to call `clear()` and return to the landing page.

## Entity URI Behavior

`entity-uri.tsx` detects static vs live mode:

- **Static mode**: colored dataset pill, click opens the raw URI in a new tab, no hover popover fetch.
- **Live mode**: behavior unchanged (popover via `useEntityQuery`).

Detection via a simple `isStatic` flag passed through context or prop, not a provider abstraction.

## Session Export

### Session Picker Refactor (`session-picker.tsx`)

- Replace current dropdown with shadcn `Select` component
- Each session item shows: session ID, message count, time range
- **Export button** (download icon) on each session row
- Current/live session indicated with a green dot
- Export downloads JSONL with `session_meta` preamble prepended

### Toolbar Export

New button in the existing viewer toolbar:
- Downloads current session's JSONL
- Disabled if no active session

### Server-Side Export Endpoint

Add query param support to the existing sessions endpoint:

`GET /viewer/api/sessions/{id}?format=jsonl`

Returns raw JSONL text with:
- `Content-Type: text/plain`
- `Content-Disposition: attachment; filename="linked-past-{session_id}.jsonl"`
- Line 1: `session_meta` preamble
- Lines 2+: raw messages as recorded

## Build Configuration

### Vite Config Changes

Two build targets in `vite.config.ts`:

- `npm run build` — existing live viewer, `base: "/viewer/"`, output to `dist/`
- `npm run build:static` — static viewer, `base: "/linked-past/"`, output to `dist-static/`, entry point `static.html`

### GitHub Actions (`.github/workflows/deploy-viewer.yml`)

- **Trigger**: push to `main` when files in `packages/linked-past-viewer/` change
- **Steps**:
  1. Checkout
  2. Setup Node
  3. `npm ci` in `packages/linked-past-viewer/`
  4. `npm run build:static`
  5. Deploy `dist-static/` to GitHub Pages via `actions/deploy-pages@v4`
- **Base path**: `/linked-past/` (for `gillisandrew.github.io/linked-past/`)

## Roadmap (Post-MVP)

- **Entity popover fetching** — resolve entity URIs against a lightweight API or pre-baked entity index
- **Gist sharing** — URL hash with `#gist={id}`, backend proxy to fetch and validate (avoids CORS), auto-loads on page open
- **Versioned deployments** — tagged releases with version in URL
