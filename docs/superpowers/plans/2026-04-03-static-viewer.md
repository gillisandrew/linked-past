# Static Session Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy a GitHub Pages viewer that loads session JSONL files via paste/upload and renders them in the same feed interface as the live viewer.

**Architecture:** Second Vite entry point in the existing `linked-past-viewer` package. Zod schemas validate messages at the boundary for both live and static viewers. Shared rendering components (Feed, MarkdownReport, MermaidBlock, etc.) are reused unchanged. Entity URI pills link out instead of fetching popovers.

**Tech Stack:** React 19, Vite 8, Zod 3, Tailwind v4, shadcn/ui, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-04-03-static-viewer-design.md`

---

### Task 1: Add Zod dependency and create message schemas

**Files:**
- Modify: `packages/linked-past-viewer/package.json`
- Create: `packages/linked-past-viewer/src/lib/schemas.ts`
- Modify: `packages/linked-past-viewer/src/lib/types.ts`

- [ ] **Step 1: Add zod as a direct dependency**

Zod is already available transitively via shadcn, but it should be a direct dependency since we use it in application code.

```bash
cd packages/linked-past-viewer && npm install zod
```

- [ ] **Step 2: Create `src/lib/schemas.ts` with all message schemas**

```typescript
import { z } from "zod";

// --- Session metadata preamble ---

export const SessionMetaSchema = z.object({
  format_version: z.number().int().positive(),
  type: z.literal("session_meta"),
  session_id: z.string(),
  created_at: z.string(),
});

// --- Data schemas per message type ---

const PredicateMetaSchema = z.object({
  label: z.string().optional(),
  comment: z.string().optional(),
  domain: z.string().optional(),
  range: z.string().optional(),
});

const XrefLinkSchema = z.object({
  target: z.string(),
  relationship: z.string(),
  confidence: z.string(),
  basis: z.string(),
});

export const QueryDataSchema = z.object({
  rows: z.array(z.record(z.string(), z.string())),
  columns: z.array(z.string()),
  sparql: z.string(),
  row_count: z.number(),
  prefix_map: z.record(z.string(), z.string()).optional(),
  title: z.string().nullish(),
});

export const EntityDataSchema = z.object({
  uri: z.string(),
  name: z.string(),
  dataset: z.string().nullable(),
  description: z.string().optional(),
  type_hierarchy: z.array(z.string()).optional(),
  see_also: z.array(z.string()).optional(),
  properties: z.array(z.object({ pred: z.string(), obj: z.string() })),
  predicate_meta: z.record(z.string(), PredicateMetaSchema).optional(),
  xrefs: z.array(XrefLinkSchema),
});

export const LinksDataSchema = z.object({
  uri: z.string(),
  links: z.array(XrefLinkSchema),
});

export const SearchDataSchema = z.object({
  query_text: z.string(),
  results: z.array(
    z.object({ uri: z.string(), label: z.string(), dataset: z.string() }),
  ),
});

export const ReportDataSchema = z.object({
  title: z.string().nullable(),
  markdown: z.string(),
});

// --- Base message fields ---

const BaseMessageFields = {
  session_id: z.string(),
  seq: z.number(),
  dataset: z.string().nullable(),
  timestamp: z.string(),
};

// --- Discriminated union ---

export const ViewerMessageSchema = z.discriminatedUnion("type", [
  z.object({ ...BaseMessageFields, type: z.literal("query"), data: QueryDataSchema }),
  z.object({ ...BaseMessageFields, type: z.literal("entity"), data: EntityDataSchema }),
  z.object({ ...BaseMessageFields, type: z.literal("links"), data: LinksDataSchema }),
  z.object({ ...BaseMessageFields, type: z.literal("search"), data: SearchDataSchema }),
  z.object({ ...BaseMessageFields, type: z.literal("report"), data: ReportDataSchema }),
]);

// --- Inferred types ---

export type SessionMeta = z.infer<typeof SessionMetaSchema>;
export type ViewerMessage = z.infer<typeof ViewerMessageSchema>;
export type QueryData = z.infer<typeof QueryDataSchema>;
export type EntityData = z.infer<typeof EntityDataSchema>;
export type LinksData = z.infer<typeof LinksDataSchema>;
export type SearchData = z.infer<typeof SearchDataSchema>;
export type ReportData = z.infer<typeof ReportDataSchema>;
export type XrefLink = z.infer<typeof XrefLinkSchema>;
export type PredicateMeta = z.infer<typeof PredicateMetaSchema>;
```

- [ ] **Step 3: Update `src/lib/types.ts` to re-export from schemas**

Replace the hand-written type definitions with re-exports. Keep the `SessionInfo` type (used by the session picker, not part of the message format).

```typescript
// Message types — inferred from Zod schemas (single source of truth)
export type {
  ViewerMessage,
  QueryData,
  EntityData,
  LinksData,
  SearchData,
  ReportData,
  XrefLink,
  PredicateMeta,
  SessionMeta,
} from "./schemas";

// Session list item (from /viewer/api/sessions, not part of JSONL format)
export type SessionInfo = {
  id: string;
  message_count: number;
  started: string;
  last_activity: string;
  is_current: boolean;
};
```

- [ ] **Step 4: Verify the existing viewer still type-checks**

```bash
cd packages/linked-past-viewer && npx tsc --noEmit
```

Expected: no errors. The inferred types should be structurally identical to the hand-written ones.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-viewer/package.json packages/linked-past-viewer/package-lock.json packages/linked-past-viewer/src/lib/schemas.ts packages/linked-past-viewer/src/lib/types.ts
git commit -m "feat(viewer): add Zod message schemas, infer types from schemas"
```

---

### Task 2: Create JSONL parser with validation

**Files:**
- Create: `packages/linked-past-viewer/src/lib/parse-session.ts`

- [ ] **Step 1: Create `src/lib/parse-session.ts`**

```typescript
import { ViewerMessageSchema, SessionMetaSchema } from "./schemas";
import type { ViewerMessage } from "./schemas";

export type ParseError = {
  line: number;
  raw: string;
  error: string;
};

export type ParseResult = {
  messages: ViewerMessage[];
  errors: ParseError[];
  formatVersion: number | null;
};

export function parseSessionJsonl(text: string): ParseResult {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== "");
  const messages: ViewerMessage[] = [];
  const errors: ParseError[] = [];
  let formatVersion: number | null = null;

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const lineNum = i + 1;

    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      errors.push({
        line: lineNum,
        raw: raw.length > 200 ? raw.slice(0, 200) + "…" : raw,
        error: "Invalid JSON",
      });
      continue;
    }

    // Check for session_meta preamble
    const meta = SessionMetaSchema.safeParse(parsed);
    if (meta.success) {
      formatVersion = meta.data.format_version;
      continue;
    }

    // Validate as a viewer message
    const result = ViewerMessageSchema.safeParse(parsed);
    if (result.success) {
      messages.push(result.data);
    } else {
      const firstIssue = result.error.issues[0];
      const path = firstIssue?.path.join(".") || "";
      const reason = firstIssue?.message || "Validation failed";
      errors.push({
        line: lineNum,
        raw: raw.length > 200 ? raw.slice(0, 200) + "…" : raw,
        error: path ? `${path}: ${reason}` : reason,
      });
    }
  }

  messages.sort((a, b) => a.seq - b.seq);

  return { messages, errors, formatVersion };
}
```

- [ ] **Step 2: Verify type-check passes**

```bash
cd packages/linked-past-viewer && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past-viewer/src/lib/parse-session.ts
git commit -m "feat(viewer): add JSONL parser with Zod validation and format versioning"
```

---

### Task 3: Add static mode context for entity URIs

**Files:**
- Create: `packages/linked-past-viewer/src/lib/static-context.ts`
- Modify: `packages/linked-past-viewer/src/components/entity-uri.tsx`

- [ ] **Step 1: Create `src/lib/static-context.ts`**

```typescript
import { createContext, useContext } from "react";

const StaticModeContext = createContext(false);

export const StaticModeProvider = StaticModeContext.Provider;

export function useIsStaticMode(): boolean {
  return useContext(StaticModeContext);
}
```

- [ ] **Step 2: Modify `entity-uri.tsx` to skip popover in static mode**

The existing component renders a `pill` variable (a `<span>` with inline dataset styles) and wraps it in a `Popover`. In static mode, we skip the popover entirely and wrap the pill in a plain `<a>` tag.

Replace the entire file with:

```typescript
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useState } from "react";
import { useEntityQuery } from "../hooks/use-entity-query";
import { datasetForUri, linkHref, shortUri } from "../lib/uri";
import { useIsStaticMode } from "@/lib/static-context";
import { EntityPopoverContent } from "./entity-popover";

function datasetStyle(dataset: string | null): React.CSSProperties {
  const ds = dataset ?? "default";
  return {
    backgroundColor: `var(--ds-${ds}-bg, var(--ds-default-bg))`,
    color: `var(--ds-${ds}-fg, var(--ds-default-fg))`,
  };
}

const PILL_CLASSES =
  "inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium cursor-pointer transition-[filter] hover:brightness-95 dark:hover:brightness-110";

export function EntityUri({ uri, display }: { uri: string; display?: string }) {
  const dataset = datasetForUri(uri);
  const isStatic = useIsStaticMode();
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useEntityQuery(uri, open);
  const label = display ?? shortUri(uri);

  const pill = (
    <span className={PILL_CLASSES} style={datasetStyle(dataset)}>
      {label}
    </span>
  );

  // Static mode: no popover, just a link to the raw URI
  if (isStatic) {
    return (
      <a href={linkHref(uri)} target="_blank" rel="noopener noreferrer" title={uri}>
        {pill}
      </a>
    );
  }

  const isFullUri = uri.startsWith("http://") || uri.startsWith("https://");

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className="inline-flex items-center cursor-pointer"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        {isFullUri ? (
          <a
            href={linkHref(uri)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
          >
            {pill}
          </a>
        ) : (
          pill
        )}
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

Note: `useEntityQuery(uri, open)` is called unconditionally (React hooks rule), but `open` is always `false` in static mode since `setOpen` is never called, so it never fetches. However, `useEntityQuery` internally calls `useQuery` from `@tanstack/react-query`, which requires a `QueryClientProvider` to exist in the tree. This is handled in Task 6 by wrapping the static app in a no-op `QueryClientProvider`.

- [ ] **Step 3: Verify type-check passes**

```bash
cd packages/linked-past-viewer && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past-viewer/src/lib/static-context.ts packages/linked-past-viewer/src/components/entity-uri.tsx
git commit -m "feat(viewer): add static mode context, entity URIs link out without popover"
```

---

### Task 4: Create the static session hook

**Files:**
- Create: `packages/linked-past-viewer/src/hooks/use-static-session.ts`

- [ ] **Step 1: Create `src/hooks/use-static-session.ts`**

```typescript
import { useState, useCallback } from "react";
import { parseSessionJsonl } from "@/lib/parse-session";
import type { ParseError } from "@/lib/parse-session";
import type { ViewerMessage } from "@/lib/schemas";

export type StaticSession = {
  messages: ViewerMessage[];
  errors: ParseError[];
  formatVersion: number | null;
  loadFromText: (text: string) => void;
  loadFromFile: (file: File) => void;
  clear: () => void;
  isLoaded: boolean;
};

export function useStaticSession(): StaticSession {
  const [messages, setMessages] = useState<ViewerMessage[]>([]);
  const [errors, setErrors] = useState<ParseError[]>([]);
  const [formatVersion, setFormatVersion] = useState<number | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  const load = useCallback((text: string) => {
    const result = parseSessionJsonl(text);
    setMessages(result.messages);
    setErrors(result.errors);
    setFormatVersion(result.formatVersion);
    setIsLoaded(true);
  }, []);

  const loadFromText = useCallback(
    (text: string) => load(text),
    [load],
  );

  const loadFromFile = useCallback(
    (file: File) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result;
        if (typeof text === "string") load(text);
      };
      reader.readAsText(file);
    },
    [load],
  );

  const clear = useCallback(() => {
    setMessages([]);
    setErrors([]);
    setFormatVersion(null);
    setIsLoaded(false);
  }, []);

  return { messages, errors, formatVersion, loadFromText, loadFromFile, clear, isLoaded };
}
```

- [ ] **Step 2: Verify type-check passes**

```bash
cd packages/linked-past-viewer && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past-viewer/src/hooks/use-static-session.ts
git commit -m "feat(viewer): add useStaticSession hook for JSONL loading"
```

---

### Task 5: Create drop zone landing page component

**Files:**
- Create: `packages/linked-past-viewer/src/components/drop-zone.tsx`

- [ ] **Step 1: Create `src/components/drop-zone.tsx`**

```typescript
import { useState, useRef, useCallback, type DragEvent } from "react";
import { Upload, ClipboardPaste, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";

export function DropZone({
  onLoadText,
  onLoadFile,
}: {
  onLoadText: (text: string) => void;
  onLoadFile: (file: File) => void;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [showPaste, setShowPaste] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) onLoadFile(file);
    },
    [onLoadFile],
  );

  const handleFileSelect = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) onLoadFile(file);
    },
    [onLoadFile],
  );

  const handlePasteLoad = useCallback(() => {
    if (pasteText.trim()) onLoadText(pasteText);
  }, [pasteText, onLoadText]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 px-4">
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          linked-past session viewer
        </h1>
        <p className="text-muted-foreground">
          Drop a session <code className="text-xs bg-muted px-1.5 py-0.5 rounded">.jsonl</code> file or paste its contents to browse
        </p>
      </div>

      {/* Drop zone */}
      <div
        className={`w-full max-w-lg border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
          isDragging
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-muted-foreground/50"
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleFileSelect}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".jsonl"
          className="hidden"
          onChange={handleFileChange}
        />
        <div className="flex flex-col items-center gap-3">
          {isDragging ? (
            <FileText className="w-10 h-10 text-primary" />
          ) : (
            <Upload className="w-10 h-10 text-muted-foreground" />
          )}
          <p className="text-sm text-muted-foreground">
            {isDragging ? "Drop to load" : "Drag & drop or click to browse"}
          </p>
        </div>
      </div>

      {/* Paste toggle */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setShowPaste(!showPaste)}
        className="text-muted-foreground"
      >
        <ClipboardPaste className="w-4 h-4 mr-2" />
        {showPaste ? "Hide paste area" : "Or paste JSONL content"}
      </Button>

      {/* Paste area */}
      {showPaste && (
        <div className="w-full max-w-lg space-y-3">
          <textarea
            className="w-full h-40 rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-ring"
            placeholder='{"session_id":"...","seq":1,"type":"query",...}'
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
          />
          <Button
            onClick={handlePasteLoad}
            disabled={!pasteText.trim()}
            className="w-full"
          >
            Load session
          </Button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify type-check passes**

```bash
cd packages/linked-past-viewer && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past-viewer/src/components/drop-zone.tsx
git commit -m "feat(viewer): add DropZone component for file upload and paste"
```

---

### Task 6: Create static viewer entry point and HTML

**Files:**
- Create: `packages/linked-past-viewer/static.html`
- Create: `packages/linked-past-viewer/src/static.tsx`

- [ ] **Step 1: Create `static.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>linked-past session viewer</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/static.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Create `src/static.tsx`**

This is the static viewer app shell. It shows the DropZone when no session is loaded, and the Feed when one is. Parse errors render as inline warning items in the feed.

Note: The static app needs a no-op `QueryClientProvider` because shared components (entity-uri → useEntityQuery → useQuery) require one in the React tree, even though no fetches are made in static mode.

```typescript
import "./app.css";

import { createRoot } from "react-dom/client";
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DropZone } from "@/components/drop-zone";
import { Feed } from "@/components/feed";
import { StaticModeProvider } from "@/lib/static-context";
import { useStaticSession } from "@/hooks/use-static-session";
import { Button } from "@/components/ui/button";
import { FolderOpen, ChevronDown, ChevronUp, AlertTriangle } from "lucide-react";

const CURRENT_FORMAT_VERSION = 1;
const queryClient = new QueryClient();

function StaticApp() {
  const session = useStaticSession();
  const [forceOpen, setForceOpen] = useState<{ value: boolean; rev: number } | null>(null);

  if (!session.isLoaded) {
    return <DropZone onLoadText={session.loadFromText} onLoadFile={session.loadFromFile} />;
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center justify-between px-4 h-12">
          <span className="text-sm font-medium">
            linked-past session viewer
          </span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {session.messages.length} items
              {session.errors.length > 0 && `, ${session.errors.length} errors`}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              title="Expand all"
              onClick={() =>
                setForceOpen((p) => ({ value: true, rev: (p?.rev ?? 0) + 1 }))
              }
            >
              <ChevronDown className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              title="Collapse all"
              onClick={() =>
                setForceOpen((p) => ({ value: false, rev: (p?.rev ?? 0) + 1 }))
              }
            >
              <ChevronUp className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm" onClick={session.clear}>
              <FolderOpen className="h-4 w-4 mr-1" />
              Load another
            </Button>
          </div>
        </div>
      </header>

      {/* Format version warning */}
      {session.formatVersion !== null &&
        session.formatVersion > CURRENT_FORMAT_VERSION && (
          <div className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-700 dark:text-amber-400 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            This session was created with a newer format (v{session.formatVersion}).
            Some items may not render correctly.
          </div>
        )}

      {/* Parse errors — shown as a collapsible banner above the feed */}
      {session.errors.length > 0 && (
        <div className="border-b border-amber-500/30 bg-amber-500/5 px-4 py-3 space-y-2">
          <p className="text-xs font-medium text-amber-700 dark:text-amber-400">
            {session.errors.length} line{session.errors.length !== 1 ? "s" : ""} could not be parsed:
          </p>
          {session.errors.map((err) => (
            <div
              key={err.line}
              className="text-xs font-mono bg-amber-500/10 rounded px-2 py-1.5 border border-amber-500/20"
            >
              <span className="text-amber-600 dark:text-amber-400 font-semibold">
                Line {err.line}:
              </span>{" "}
              <span className="text-muted-foreground">{err.error}</span>
              <div className="mt-1 text-muted-foreground/70 truncate">
                {err.raw}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Feed */}
      <div className="p-4">
        <Feed
          messages={session.messages}
          bookmarks={new Set()}
          notes={new Map()}
          forceOpen={forceOpen}
        />
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <StaticModeProvider value={true}>
      <StaticApp />
    </StaticModeProvider>
  </QueryClientProvider>,
);
```

- [ ] **Step 3: Verify type-check passes**

```bash
cd packages/linked-past-viewer && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past-viewer/static.html packages/linked-past-viewer/src/static.tsx
git commit -m "feat(viewer): add static viewer entry point and app shell"
```

---

### Task 7: Add static build target to Vite config and package.json

**Files:**
- Modify: `packages/linked-past-viewer/vite.config.ts`
- Modify: `packages/linked-past-viewer/package.json`

- [ ] **Step 1: Modify `vite.config.ts`**

The existing config uses a single `base: "/viewer/"`. Add a mode-based switch so `build:static` uses `base: "/linked-past/"` and a different entry/output.

Read the current file to get the exact contents, then replace the `defineConfig` call with:

```typescript
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const isStatic = process.env.BUILD_STATIC === "1";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: isStatic ? "/linked-past/" : "/viewer/",
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
    outDir: isStatic ? "dist-static" : "dist",
    rollupOptions: isStatic
      ? { input: path.resolve(__dirname, "static.html") }
      : undefined,
  },
});
```

- [ ] **Step 2: Install `cross-env` and add `build:static` script**

`BUILD_STATIC=1 command` is Unix-only syntax. Use `cross-env` for cross-platform support.

```bash
cd packages/linked-past-viewer && npm install --save-dev cross-env
```

Add to the `"scripts"` section of `package.json`:

```json
"build:static": "cross-env BUILD_STATIC=1 tsc --noEmit && cross-env BUILD_STATIC=1 vite build"
```

- [ ] **Step 3: Test the static build**

```bash
cd packages/linked-past-viewer && npm run build:static
```

Expected: builds to `dist-static/` with `static.html` as the entry point. Check:

```bash
ls dist-static/
```

Should contain `static.html` and `assets/` directory.

- [ ] **Step 4: Test the existing build still works**

```bash
cd packages/linked-past-viewer && npm run build
```

Expected: builds to `dist/` as before, unchanged.

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-viewer/vite.config.ts packages/linked-past-viewer/package.json
git commit -m "feat(viewer): add static build target (BUILD_STATIC=1 vite build)"
```

---

### Task 8: Write session_meta preamble from Python ViewerManager

**Files:**
- Modify: `packages/linked-past/linked_past/core/viewer.py`

- [ ] **Step 1: Modify `ViewerManager.activate()` to write session_meta line**

Read the current `activate()` method in `packages/linked-past/linked_past/core/viewer.py`. After the session file is opened, add:

```python
import json as _json

# In activate(), after self._session_file = open(...):
meta = _json.dumps({
    "format_version": 1,
    "type": "session_meta",
    "session_id": self._session_id,
    "created_at": datetime.now(timezone.utc).isoformat(),
})
self._session_file.write(meta + "\n")
self._session_file.flush()
```

Make sure the `json` import doesn't conflict with any existing import at the top of the file — use the module-level `import json` if one already exists, or add it.

- [ ] **Step 2: Run existing tests to verify no regressions**

```bash
cd /Users/gillisandrew/Projects/gillisandrew/dprr-tool && uv run pytest packages/linked-past/tests/ -x -q
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past/linked_past/core/viewer.py
git commit -m "feat(viewer): write session_meta preamble to JSONL on session start"
```

---

### Task 9: Add JSONL export endpoint to Python viewer API

**Files:**
- Modify: `packages/linked-past/linked_past/core/viewer_api.py`

- [ ] **Step 1: Add `datetime` import and modify `session_detail_handler` to support `?format=jsonl`**

Read the current `session_detail_handler` in `packages/linked-past/linked_past/core/viewer_api.py`.

First, ensure these imports exist at the module level (add if missing):

```python
import json
from datetime import datetime, timezone
```

Then modify the handler. **Important:** Do NOT add a viewer-active guard (`mgr.is_active` check). The existing handler serves session files from disk regardless of whether the viewer is currently running — this is correct behavior since users need to export past sessions without requiring an active MCP session.

Add a `format` query param branch to the existing handler. Keep the existing path-traversal and existence checks unchanged, then add the `jsonl` format branch before the existing JSON response:

```python
    # After existing session_file existence check, before existing JSON response:

    fmt = request.query_params.get("format", "json")

    if fmt == "jsonl":
        content = session_file.read_text()
        # Ensure session_meta preamble exists (for sessions created before this feature)
        if not content.startswith('{"format_version"'):
            lines = content.strip().splitlines()
            first = json.loads(lines[0]) if lines else {}
            meta = json.dumps({
                "format_version": 1,
                "type": "session_meta",
                "session_id": session_id,
                "created_at": first.get("timestamp", datetime.now(timezone.utc).isoformat()),
            })
            content = meta + "\n" + content

        return PlainTextResponse(
            content,
            headers={
                "Content-Disposition": f'attachment; filename="linked-past-{session_id}.jsonl"',
            },
        )

    # ... existing JSON response code continues unchanged
```

- [ ] **Step 2: Run existing tests**

```bash
cd /Users/gillisandrew/Projects/gillisandrew/dprr-tool && uv run pytest packages/linked-past/tests/ -x -q
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past/linked_past/core/viewer_api.py
git commit -m "feat(viewer): add ?format=jsonl export endpoint for sessions"
```

---

### Task 10: Refactor session picker with shadcn Select and export buttons

**Files:**
- Create: `packages/linked-past-viewer/src/components/ui/select.tsx` (via shadcn CLI)
- Modify: `packages/linked-past-viewer/src/components/session-picker.tsx`

- [ ] **Step 1: Install shadcn Select component**

The `Select` component is not yet installed. Add it:

```bash
cd packages/linked-past-viewer && npx shadcn@latest add select
```

This creates `src/components/ui/select.tsx` with `Select`, `SelectTrigger`, `SelectContent`, `SelectItem`, etc.

- [ ] **Step 2: Rewrite `session-picker.tsx`**

Read the current file to understand the exact props and behavior. Replace the implementation with a shadcn `Select`-based component. Keep the same component signature (`SessionPicker` with `onLoadSession`, `onBackToLive`, `viewingSessionId`, `initialSessionId` props).

Key changes:
1. Replace the custom dropdown with shadcn `Select` / `SelectTrigger` / `SelectContent` / `SelectItem`
2. Add a download icon button per session item that fetches `/viewer/api/sessions/{id}?format=jsonl` and triggers a browser download
3. Show a green dot for the current live session
4. Show message count and time range per item

The export download handler:

```typescript
const handleExport = useCallback(async (sessionId: string, e: React.MouseEvent) => {
  e.stopPropagation();
  const res = await fetch(`/viewer/api/sessions/${sessionId}?format=jsonl`);
  if (!res.ok) return;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `linked-past-${sessionId}.jsonl`;
  a.click();
  URL.revokeObjectURL(url);
}, []);
```

Use `Download` from `lucide-react` for the export icon.

- [ ] **Step 3: Verify type-check passes**

```bash
cd packages/linked-past-viewer && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past-viewer/src/components/ui/select.tsx packages/linked-past-viewer/src/components/session-picker.tsx
git commit -m "refactor(viewer): session picker with shadcn Select and JSONL export"
```

---

### Task 11: Add toolbar export button for current session

**Files:**
- Modify: `packages/linked-past-viewer/src/components/viewer-layout.tsx`

- [ ] **Step 1: Add JSONL export button to the toolbar in `viewer-layout.tsx`**

Read the current file. The toolbar already has an `ExportButton` that exports as **Markdown**. Add a second button for **JSONL export** — use `FileDown` (not `Download`) from `lucide-react` to visually distinguish from the existing Markdown export which uses `Download`. Add a tooltip to make the distinction clear.

Add a memoized `liveSessionId` near the top of `ViewerLayout`:

```typescript
const liveSessionId = useMemo(
  () => (liveMessages.length > 0 ? liveMessages[0].session_id : null),
  [liveMessages],
);
```

Then add the export handler — use `liveMessages` in the dependency array (not the derived `liveSessionId`):

```typescript
const handleExportJsonl = useCallback(async () => {
  const sessionId = pastSession?.id ?? liveSessionId;
  if (!sessionId) return;
  const res = await fetch(`/viewer/api/sessions/${sessionId}?format=jsonl`);
  if (!res.ok) return;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `linked-past-${sessionId}.jsonl`;
  a.click();
  URL.revokeObjectURL(url);
}, [pastSession, liveSessionId]);
```

Add the button next to the existing Markdown export button:

```tsx
<Button
  variant="ghost"
  size="icon"
  className="h-7 w-7"
  title="Export session as JSONL (for sharing)"
  disabled={!liveSessionId && !pastSession}
  onClick={handleExportJsonl}
>
  <FileDown className="h-4 w-4" />
</Button>
```

- [ ] **Step 2: Verify type-check passes**

```bash
cd packages/linked-past-viewer && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past-viewer/src/components/viewer-layout.tsx
git commit -m "feat(viewer): add toolbar button to export current session as JSONL"
```

---

### Task 12: Add Zod validation to live viewer WebSocket hook

**Files:**
- Modify: `packages/linked-past-viewer/src/hooks/use-viewer-socket.ts`

The spec lists `use-viewer-socket.ts` as "MODIFIED — add Zod parsing at boundary". Currently the live viewer does a raw `JSON.parse(e.data) as ViewerMessage` cast. Add Zod validation at the parse boundary so both viewers validate identically.

- [ ] **Step 1: Add Zod validation to the WebSocket message handler**

Read the current `use-viewer-socket.ts`. Find the `ws.onmessage` handler where `JSON.parse(e.data) as ViewerMessage` is called. Replace the cast with Zod validation:

```typescript
import { ViewerMessageSchema } from "@/lib/schemas";

// In ws.onmessage handler, replace:
//   const msg = JSON.parse(e.data) as ViewerMessage;
// with:
const parsed = ViewerMessageSchema.safeParse(JSON.parse(e.data));
if (!parsed.success) {
  console.warn("Invalid viewer message:", parsed.error.issues[0]?.message);
  return;
}
const msg = parsed.data;
```

Keep all other behavior unchanged (dedup by `seq`, session change detection, IndexedDB persistence).

- [ ] **Step 2: Verify type-check passes**

```bash
cd packages/linked-past-viewer && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past-viewer/src/hooks/use-viewer-socket.ts
git commit -m "feat(viewer): add Zod validation to WebSocket message boundary"
```

---

### Task 13: Create GitHub Actions deployment workflow

**Files:**
- Create: `.github/workflows/deploy-viewer.yml`

- [ ] **Step 1: Create `.github/workflows/deploy-viewer.yml`**

```yaml
name: Deploy Static Viewer

on:
  push:
    branches: [main]
    paths:
      - "packages/linked-past-viewer/**"

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version-file: packages/linked-past-viewer/.nvmrc
          cache: npm
          cache-dependency-path: packages/linked-past-viewer/package-lock.json

      - name: Install dependencies
        run: npm ci
        working-directory: packages/linked-past-viewer

      - name: Build static viewer
        run: npm run build:static
        working-directory: packages/linked-past-viewer

      - uses: actions/configure-pages@v5

      - uses: actions/upload-pages-artifact@v3
        with:
          path: packages/linked-past-viewer/dist-static

      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Create `.nvmrc`**

No `.nvmrc` exists in the viewer package. Create one:

```bash
node -v | sed 's/^v//' > packages/linked-past-viewer/.nvmrc
```

- [ ] **Step 3: Add `dist-static/` to `.gitignore`**

Check the existing `.gitignore` in `packages/linked-past-viewer/` (or the root). Add `dist-static/` if not already present.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy-viewer.yml
# Also add .nvmrc and .gitignore changes if applicable
git commit -m "ci: add GitHub Actions workflow for static viewer deployment"
```

---

### Task 14: End-to-end manual verification

**Files:** None (verification only)

- [ ] **Step 1: Build the static viewer and serve locally**

```bash
cd packages/linked-past-viewer && npm run build:static
npx serve dist-static -l 3000
```

Open `http://localhost:3000/linked-past/` in a browser.

- [ ] **Step 2: Test file upload**

Get a session JSONL file from the live viewer data directory:

```bash
ls ~/.local/share/linked-past/viewer/sessions/
```

Drop one into the static viewer. Verify:
- Feed renders with all message types (query results, entity cards, reports, etc.)
- Mermaid diagrams render
- Entity URIs show as colored pills
- Clicking an entity pill opens the URI in a new tab (no popover)
- Parse errors (if any) show as warning banners
- "Load another" returns to the landing page

- [ ] **Step 3: Test paste input**

Copy the contents of a small JSONL file, paste into the textarea, click "Load session". Verify same rendering behavior.

- [ ] **Step 4: Test the live viewer still works**

Start the linked-past server and open `http://localhost:8000/viewer`. Verify:
- WebSocket connection works
- Entity popovers still work on hover
- Session picker shows past sessions with export buttons
- Toolbar export button downloads JSONL
- Downloaded JSONL file starts with `session_meta` line

- [ ] **Step 5: Test round-trip**

Export a session from the live viewer → load it in the static viewer. Verify the content matches.
