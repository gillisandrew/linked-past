# Gist-Based Session Sharing

**Date:** 2026-04-03
**Status:** Draft
**Package:** `packages/linked-past-viewer`
**Depends on:** Static viewer (2026-04-03-static-viewer-design.md)

## Purpose

Allow users to share linked-past sessions by uploading JSONL files to a GitHub Gist and sharing a URL. The static viewer reads the gist ID from the URL hash, fetches the gist content directly from the GitHub API (CORS-compatible), and renders all `.jsonl` files as browsable sessions.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| URL format | `#<gist_id>` hash fragment | Client-side only, no server routing needed |
| Base path | `/linked-past/viewer/` | Matches live viewer path convention |
| CORS | Direct GitHub API fetch | `api.github.com` returns CORS headers, no proxy needed |
| Multi-file gists | Parse all `.jsonl` files, session picker | Gists are natural session bundles |
| Parse timing | All upfront on load | Content already in memory, parsing is cheap, instant switching |
| Rate limiting | Cache in `sessionStorage` | Avoids burning 60/hour unauthenticated limit on reloads |
| Hook architecture | Separate `useGistLoader` | Gist fetching/caching is a different concern from single-session state |

## Shareable URL

```
gillisandrew.github.io/linked-past/viewer#0d601c8a38613ed903d5fc170ea20ddb
```

The hash fragment contains only the gist ID. No `#gist=` prefix — just the raw ID.

## Data Flow

1. Static viewer reads `window.location.hash` on mount
2. Strip `#` — if non-empty, treat as gist ID
3. Check `sessionStorage` for cached response (`gist:{id}`)
4. If miss, fetch `https://api.github.com/gists/{id}`
5. On success, cache raw JSON in `sessionStorage`
6. Filter `files` object for entries where filename ends in `.jsonl`
7. Parse each file's `content` through `parseSessionJsonl()`
8. Show session picker if multiple files; auto-select the first
9. No hash → show drop zone / paste landing page (existing behavior)

## GitHub Gist API Response

The relevant fields from `GET https://api.github.com/gists/{id}`:

```json
{
  "id": "0d601c8a38613ed903d5fc170ea20ddb",
  "html_url": "https://gist.github.com/gillisandrew/0d601c8a38613ed903d5fc170ea20ddb",
  "files": {
    "samnites.jsonl": {
      "filename": "samnites.jsonl",
      "type": "text/plain",
      "size": 392511,
      "truncated": false,
      "content": "{\"format_version\": 1, ...}\n{\"session_id\": ...}\n..."
    }
  }
}
```

- `content` contains the full file content (inline, not truncated for files under ~1MB)
- `truncated: true` indicates the content was too large and must be fetched via `raw_url` instead
- Rate limit: 60 requests/hour unauthenticated per IP

## `useGistLoader` Hook

```typescript
type GistSession = {
  filename: string;
  result: ParseResult;
};

useGistLoader(gistId: string | null): {
  sessions: GistSession[];
  gistUrl: string | null;
  isLoading: boolean;
  error: string | null;
}
```

- `gistId` is `null` when no hash is present → hook is a no-op
- Checks `sessionStorage` key `gist:{id}` before fetching
- On fetch success: caches raw JSON, filters to `.jsonl` files, parses each with `parseSessionJsonl()`
- `gistUrl` is the `html_url` from the API response — used in error messages so users can visit the gist directly
- For truncated files (`truncated: true`): fetch the file content from `raw_url` instead

### Error Handling

| HTTP Status | Error Message |
|-------------|--------------|
| 404 | "Gist not found. Check the URL and try again." |
| 403 / 429 | "GitHub API rate limit exceeded. Try again in a few minutes." |
| No `.jsonl` files | "No session files found in this gist. Expected .jsonl files." |
| Network error | "Failed to fetch gist. Check your connection." |

All errors display in place of the drop zone, with:
- A link to the gist on `gist.github.com` (using `gistUrl` or constructed from the ID) so the user can download files manually — gist.github.com doesn't have the same rate limiting
- A "Load a file instead" link to fall back to the drop zone

## `useStaticSession` Changes

Add a `loadFromParseResult(result: ParseResult)` method to avoid re-parsing content that `useGistLoader` has already parsed:

```typescript
loadFromParseResult: (result: ParseResult) => void;
```

Sets messages, errors, and formatVersion directly from the pre-parsed result.

## Static App States

`StaticApp` has three modes:

1. **Gist mode** (hash present) — gist loader with session picker in header
2. **Local mode** (session loaded via drop zone/paste) — current behavior unchanged
3. **Landing** (nothing loaded, no hash) — drop zone

### Gist Mode Header

When in gist mode, the header shows:
- Session picker dropdown (shadcn `Select`, same pattern as live viewer) with filenames from the gist
- Switching sessions calls `loadFromParseResult()` with the selected session's data
- Expand/collapse all buttons (existing)
- "Load another" button → clears gist state, returns to landing

### Error State

When gist loading fails, show the error message centered (like the drop zone layout) with:
- The error text
- Link: "View gist on GitHub" → opens `gist.github.com/{id}` in new tab
- Link: "Load a file instead" → clears hash, shows drop zone

## Build Configuration

One change to `vite.config.ts`:

```typescript
base: isStatic ? "/linked-past/viewer/" : "/viewer/",
```

The GitHub Actions workflow is unchanged — deploys `dist-static/` to Pages.

## Caching

- **Key:** `gist:{id}` in `sessionStorage`
- **Value:** Raw JSON string from the API response
- **Lifetime:** Browser session (cleared on tab close)
- **Invalidation:** None — gists are treated as immutable for the duration of a browser session. User can hard-refresh to re-fetch.
