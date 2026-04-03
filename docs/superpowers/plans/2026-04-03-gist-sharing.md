# Gist-Based Session Sharing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable sharing linked-past sessions via GitHub Gist URLs — the static viewer reads the gist ID from the URL hash, fetches the gist directly from the GitHub API, and renders all `.jsonl` files as browsable sessions.

**Architecture:** A `useGistLoader` hook handles fetching, caching (sessionStorage), and parsing gist content. It composes with the existing `useStaticSession` hook (extended with `loadFromParseResult`). The static app gains a three-state model: gist mode, local mode, and landing. Security hardening is applied to Mermaid rendering and URI handling before gist sharing is enabled.

**Tech Stack:** React 19, Zod 3, GitHub Gist API (unauthenticated, CORS-compatible), sessionStorage

**Spec:** `docs/superpowers/specs/2026-04-03-gist-sharing-design.md`

---

### Task 1: Security hardening — Mermaid and URI sanitization

With gist sharing, any user can craft a JSONL file containing malicious content. Two XSS vectors must be closed before untrusted content is loaded.

**Files:**
- Modify: `packages/linked-past-viewer/src/components/mermaid-block.tsx`
- Modify: `packages/linked-past-viewer/src/lib/uri.ts`

- [ ] **Step 1: Change Mermaid security level from "loose" to "strict"**

In `packages/linked-past-viewer/src/components/mermaid-block.tsx`, find the `initialize` call (line 9-13) and change `securityLevel`:

```typescript
m.default.initialize({
  startOnLoad: false,
  theme: "default",
  securityLevel: "strict",
});
```

`"strict"` prevents Mermaid from rendering HTML tags inside node labels, blocking XSS payloads like `graph TD; A[<img src=x onerror=alert(1)>]`.

- [ ] **Step 2: Add protocol validation to `linkHref` in `uri.ts`**

In `packages/linked-past-viewer/src/lib/uri.ts`, modify the `linkHref` function to reject non-HTTP protocols. Replace the function (lines 88-96):

```typescript
export function linkHref(uri: string): string {
  let href = normalizeUri(uri).replace(/^http:\/\//, "https://");
  // Reject non-HTTPS protocols (blocks javascript:, data:, vbscript:, etc.)
  if (!href.startsWith("https://")) return "#";
  // Pleiades vocab#<id> → places/<id> (the web page for the place)
  href = href.replace(
    /^https:\/\/pleiades\.stoa\.org\/places\/vocab#(\d+)/,
    "https://pleiades.stoa.org/places/$1",
  );
  return href;
}
```

- [ ] **Step 3: Verify type-check passes**

```bash
cd packages/linked-past-viewer && npx tsc --noEmit
```

- [ ] **Step 4: Verify existing viewer builds**

```bash
npm run build
```

- [ ] **Step 5: Commit**

```bash
git add packages/linked-past-viewer/src/components/mermaid-block.tsx packages/linked-past-viewer/src/lib/uri.ts
git commit -m "security(viewer): harden Mermaid rendering and URI validation

Change Mermaid securityLevel from 'loose' to 'strict' to prevent XSS
via crafted diagram labels. Add protocol validation to linkHref to
reject non-HTTPS URIs (blocks javascript:, data: schemes)."
```

---

### Task 2: Add `loadFromParseResult` to `useStaticSession`

**Files:**
- Modify: `packages/linked-past-viewer/src/hooks/use-static-session.ts`

- [ ] **Step 1: Add `loadFromParseResult` method**

Add the import for `ParseResult` and the new method. The full updated file:

```typescript
import { useState, useCallback } from "react";
import { parseSessionJsonl } from "@/lib/parse-session";
import type { ParseError, ParseResult } from "@/lib/parse-session";
import type { ViewerMessage } from "@/lib/schemas";

export type StaticSession = {
  messages: ViewerMessage[];
  errors: ParseError[];
  formatVersion: number | null;
  loadFromText: (text: string) => void;
  loadFromFile: (file: File) => void;
  loadFromParseResult: (result: ParseResult) => void;
  clear: () => void;
  isLoaded: boolean;
};

export function useStaticSession(): StaticSession {
  const [messages, setMessages] = useState<ViewerMessage[]>([]);
  const [errors, setErrors] = useState<ParseError[]>([]);
  const [formatVersion, setFormatVersion] = useState<number | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  const applyResult = useCallback((result: ParseResult) => {
    setMessages(result.messages);
    setErrors(result.errors);
    setFormatVersion(result.formatVersion);
    setIsLoaded(true);
  }, []);

  const loadFromText = useCallback(
    (text: string) => applyResult(parseSessionJsonl(text)),
    [applyResult],
  );

  const loadFromFile = useCallback(
    (file: File) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result;
        if (typeof text === "string") applyResult(parseSessionJsonl(text));
      };
      reader.readAsText(file);
    },
    [applyResult],
  );

  const loadFromParseResult = applyResult;

  const clear = useCallback(() => {
    setMessages([]);
    setErrors([]);
    setFormatVersion(null);
    setIsLoaded(false);
  }, []);

  return {
    messages,
    errors,
    formatVersion,
    loadFromText,
    loadFromFile,
    loadFromParseResult,
    clear,
    isLoaded,
  };
}
```

- [ ] **Step 2: Verify type-check passes**

```bash
cd packages/linked-past-viewer && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past-viewer/src/hooks/use-static-session.ts
git commit -m "feat(viewer): add loadFromParseResult to useStaticSession"
```

---

### Task 3: Create `useGistLoader` hook

**Files:**
- Create: `packages/linked-past-viewer/src/hooks/use-gist-loader.ts`

- [ ] **Step 1: Create the hook**

```typescript
import { useEffect, useState } from "react";
import { z } from "zod";
import { parseSessionJsonl } from "@/lib/parse-session";
import type { ParseResult } from "@/lib/parse-session";

export type GistSession = {
  filename: string;
  result: ParseResult;
};

const GistFileSchema = z.object({
  filename: z.string(),
  type: z.string(),
  size: z.number(),
  truncated: z.boolean(),
  raw_url: z.string().url(),
  content: z.string(),
});

const GistResponseSchema = z.object({
  id: z.string(),
  html_url: z.string().url(),
  files: z.record(z.string(), GistFileSchema),
});

type GistResponse = z.infer<typeof GistResponseSchema>;

const CACHE_PREFIX = "gist:";

function getCached(gistId: string): GistResponse | null {
  try {
    const raw = sessionStorage.getItem(CACHE_PREFIX + gistId);
    return raw ? (JSON.parse(raw) as GistResponse) : null;
  } catch {
    return null;
  }
}

function setCache(gistId: string, data: GistResponse): void {
  try {
    sessionStorage.setItem(CACHE_PREFIX + gistId, JSON.stringify(data));
  } catch {
    // sessionStorage full or unavailable — ignore
  }
}

async function fetchFileContent(file: GistFile): Promise<string> {
  if (!file.truncated) return file.content;
  const res = await fetch(file.raw_url);
  if (!res.ok) throw new Error(`Failed to fetch ${file.filename}`);
  return res.text();
}

async function loadGist(gistId: string): Promise<{
  sessions: GistSession[];
  gistUrl: string;
}> {
  let data = getCached(gistId);

  if (!data) {
    const res = await fetch(`https://api.github.com/gists/${gistId}`);
    if (res.status === 404) throw new Error("Gist not found. Check the URL and try again.");
    if (res.status === 403 || res.status === 429) {
      throw new Error("GitHub API rate limit exceeded. Try again in a few minutes.");
    }
    if (!res.ok) throw new Error("Failed to fetch gist. Check your connection.");
    const json = await res.json();
    const parsed = GistResponseSchema.safeParse(json);
    if (!parsed.success) throw new Error("Unexpected gist response format.");
    data = parsed.data;
    setCache(gistId, data);
  }

  const jsonlFiles = Object.values(data.files).filter((f) =>
    f.filename.endsWith(".jsonl"),
  );

  if (jsonlFiles.length === 0) {
    throw new Error("No session files found in this gist. Expected .jsonl files.");
  }

  const sessions: GistSession[] = await Promise.all(
    jsonlFiles.map(async (file) => {
      const content = await fetchFileContent(file);
      return { filename: file.filename, result: parseSessionJsonl(content) };
    }),
  );

  return { sessions, gistUrl: data.html_url };
}

export function useGistLoader(gistId: string | null): {
  sessions: GistSession[];
  gistUrl: string | null;
  isLoading: boolean;
  error: string | null;
} {
  const [sessions, setSessions] = useState<GistSession[]>([]);
  const [gistUrl, setGistUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!gistId) return;

    let cancelled = false;
    setIsLoading(true);
    setError(null);
    setSessions([]);
    setGistUrl(null);

    loadGist(gistId)
      .then(({ sessions, gistUrl }) => {
        if (cancelled) return;
        setSessions(sessions);
        setGistUrl(gistUrl);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [gistId]);

  return { sessions, gistUrl, isLoading, error };
}
```

- [ ] **Step 2: Verify type-check passes**

```bash
cd packages/linked-past-viewer && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past-viewer/src/hooks/use-gist-loader.ts
git commit -m "feat(viewer): add useGistLoader hook with sessionStorage caching"
```

---

### Task 4: Update static app with gist mode and session picker

**Files:**
- Modify: `packages/linked-past-viewer/src/static.tsx`

- [ ] **Step 1: Rewrite `static.tsx` to support three modes**

The static app now has three states: gist mode (hash present), local mode (file/paste loaded), and landing (drop zone). Read the current file, then replace it entirely:

```typescript
import "./app.css";

import { createRoot } from "react-dom/client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DropZone } from "@/components/drop-zone";
import { Feed } from "@/components/feed";
import { StaticModeProvider } from "@/lib/static-context";
import { useStaticSession } from "@/hooks/use-static-session";
import { useGistLoader } from "@/hooks/use-gist-loader";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import {
  FolderOpen,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Loader2,
  ExternalLink,
} from "lucide-react";

const CURRENT_FORMAT_VERSION = 1;
const queryClient = new QueryClient();

function getGistId(): string | null {
  const hash = window.location.hash.slice(1);
  // Validate gist ID format: 20-32 hex chars (blocks path traversal)
  return /^[a-f0-9]{20,32}$/.test(hash) ? hash : null;
}

function StaticApp() {
  const [gistId, setGistId] = useState(getGistId);
  const gist = useGistLoader(gistId);
  const session = useStaticSession();
  const [forceOpen, setForceOpen] = useState<{
    value: boolean;
    rev: number;
  } | null>(null);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);

  // Listen for hash changes (back/forward navigation)
  useEffect(() => {
    const onHashChange = () => setGistId(getGistId());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  // Destructure stable callbacks to avoid stale-reference issues in effects
  const { loadFromParseResult, clear: clearSession } = session;

  // Auto-select first session when gist loads
  useEffect(() => {
    if (gist.sessions.length > 0 && !selectedFilename) {
      const first = gist.sessions[0];
      setSelectedFilename(first.filename);
      loadFromParseResult(first.result);
    }
  }, [gist.sessions, selectedFilename, loadFromParseResult]);

  const handleSessionChange = useCallback(
    (filename: string | null) => {
      if (!filename) return;
      const match = gist.sessions.find((s) => s.filename === filename);
      if (match) {
        setSelectedFilename(filename);
        loadFromParseResult(match.result);
      }
    },
    [gist.sessions, loadFromParseResult],
  );

  const handleClearAll = useCallback(() => {
    clearSession();
    setGistId(null);
    setSelectedFilename(null);
    history.replaceState(null, "", window.location.pathname + window.location.search);
  }, [clearSession]);

  // --- Gist loading state ---
  if (gistId && gist.isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Loading gist…</p>
      </div>
    );
  }

  // --- Gist error state ---
  if (gistId && gist.error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 px-4 text-center">
        <AlertTriangle className="h-10 w-10 text-amber-500" />
        <p className="text-sm text-foreground">{gist.error}</p>
        <div className="flex items-center gap-3 text-sm">
          <a
            href={`https://gist.github.com/${gistId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary underline inline-flex items-center gap-1"
          >
            View gist on GitHub <ExternalLink className="h-3 w-3" />
          </a>
          <span className="text-muted-foreground">·</span>
          <button
            onClick={handleClearAll}
            className="text-primary underline cursor-pointer"
          >
            Load a file instead
          </button>
        </div>
      </div>
    );
  }

  // --- Landing (no gist, no session loaded) ---
  if (!session.isLoaded) {
    return (
      <DropZone
        onLoadText={session.loadFromText}
        onLoadFile={session.loadFromFile}
      />
    );
  }

  // --- Session loaded (gist or local) ---
  const isGistMode = gistId !== null && gist.sessions.length > 0;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center justify-between px-4 h-12">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium">linked-past</span>
            {isGistMode && gist.sessions.length > 1 && (
              <Select
                value={selectedFilename ?? ""}
                onValueChange={handleSessionChange}
              >
                <SelectTrigger size="sm" className="min-w-[160px] text-xs">
                  <span className="flex flex-1 text-left truncate">
                    {selectedFilename ?? "Select session"}
                  </span>
                </SelectTrigger>
                <SelectContent align="start" alignItemWithTrigger={false}>
                  {gist.sessions.map((s) => (
                    <SelectItem key={s.filename} value={s.filename}>
                      {s.filename.replace(/\.jsonl$/, "")} ·{" "}
                      {s.result.messages.length} items
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            {isGistMode && gist.sessions.length === 1 && (
              <span className="text-xs text-muted-foreground">
                {gist.sessions[0].filename.replace(/\.jsonl$/, "")}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {session.messages.length} items
              {session.errors.length > 0 &&
                `, ${session.errors.length} errors`}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              title="Expand all"
              onClick={() =>
                setForceOpen((p) => ({
                  value: true,
                  rev: (p?.rev ?? 0) + 1,
                }))
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
                setForceOpen((p) => ({
                  value: false,
                  rev: (p?.rev ?? 0) + 1,
                }))
              }
            >
              <ChevronUp className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm" onClick={handleClearAll}>
              <FolderOpen className="h-4 w-4 mr-1" />
              Load another
            </Button>
          </div>
        </div>
      </header>

      {session.formatVersion !== null &&
        session.formatVersion > CURRENT_FORMAT_VERSION && (
          <div className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-700 dark:text-amber-400 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            This session was created with a newer format (v
            {session.formatVersion}). Some items may not render correctly.
          </div>
        )}

      {session.errors.length > 0 && (
        <div className="border-b border-amber-500/30 bg-amber-500/5 px-4 py-3 space-y-2">
          <p className="text-xs font-medium text-amber-700 dark:text-amber-400">
            {session.errors.length} line
            {session.errors.length !== 1 ? "s" : ""} could not be parsed:
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

- [ ] **Step 2: Verify type-check passes**

```bash
cd packages/linked-past-viewer && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add packages/linked-past-viewer/src/static.tsx
git commit -m "feat(viewer): add gist mode with session picker to static viewer"
```

---

### Task 5: Update Vite base path and rebuild

**Files:**
- Modify: `packages/linked-past-viewer/vite.config.ts`

- [ ] **Step 1: Change the static base path**

In `packages/linked-past-viewer/vite.config.ts`, change the static base from `/linked-past/` to `/linked-past/viewer/`:

```typescript
base: isStatic ? "/linked-past/viewer/" : "/viewer/",
```

- [ ] **Step 2: Test static build**

```bash
cd packages/linked-past-viewer && npm run build:static
```

Expected: builds to `dist-static/` successfully.

- [ ] **Step 3: Test existing build still works**

```bash
npm run build
```

Expected: builds to `dist/` unchanged.

- [ ] **Step 4: Commit**

```bash
git add packages/linked-past-viewer/vite.config.ts
git commit -m "feat(viewer): update static base path to /linked-past/viewer/"
```

---

### Task 6: End-to-end verification

**Files:** None (verification only)

- [ ] **Step 1: Test gist loading locally**

```bash
cd packages/linked-past-viewer && npm run build:static && npm run preview:static
```

Open the URL Vite prints (e.g., `http://localhost:4173/linked-past/viewer/`). Verify:
- Drop zone appears when no hash
- Append `#0d601c8a38613ed903d5fc170ea20ddb` to the URL
- Loading spinner appears, then session renders
- Feed shows query results, entity cards, reports, mermaid diagrams
- Entity URIs render as colored pills that open in new tab
- "Load another" clears the session and returns to drop zone

- [ ] **Step 2: Test security hardening**

Verify Mermaid XSS is blocked: Create a test JSONL file with a malicious mermaid block:

```json
{"format_version": 1, "type": "session_meta", "session_id": "test", "created_at": "2026-01-01T00:00:00Z"}
{"session_id": "test", "seq": 1, "type": "report", "dataset": null, "timestamp": "2026-01-01T00:00:00Z", "data": {"title": "XSS Test", "markdown": "```mermaid\ngraph TD\n  A[<img src=x onerror=alert('xss')>]\n```"}}
```

Upload this file to the static viewer. The mermaid diagram should render the node label as escaped text, NOT execute the JavaScript.

- [ ] **Step 3: Test error states**

- Append `#nonexistent_gist_id_12345` → should show "Gist not found" with link to GitHub
- Test "Load a file instead" link returns to drop zone
- Test "View gist on GitHub" link opens in new tab

- [ ] **Step 4: Test multi-file gist**

Create a gist with two `.jsonl` files. Load it via hash. Verify:
- Session picker dropdown appears in the header
- Switching between sessions loads different data
- Item counts update correctly

- [ ] **Step 5: Test sessionStorage caching**

Load a gist via hash. Reload the page. Verify the gist loads instantly (from cache, no network request in DevTools Network tab).
