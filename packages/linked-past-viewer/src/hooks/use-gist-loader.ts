import { useEffect, useState, useRef } from "react";
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
const STALE_MS = 60_000; // 1 minute

type CacheEntry = {
  data: GistResponse;
  ts: number;
};

function getCached(gistId: string): CacheEntry | null {
  try {
    const raw = sessionStorage.getItem(CACHE_PREFIX + gistId);
    if (!raw) return null;
    const entry = JSON.parse(raw) as { data: unknown; ts: number };
    const parsed = GistResponseSchema.safeParse(entry.data);
    return parsed.success ? { data: parsed.data, ts: entry.ts } : null;
  } catch {
    return null;
  }
}

function setCache(gistId: string, data: GistResponse): void {
  try {
    const entry: CacheEntry = { data, ts: Date.now() };
    sessionStorage.setItem(CACHE_PREFIX + gistId, JSON.stringify(entry));
  } catch {
    // sessionStorage full or unavailable — ignore
  }
}

async function fetchFileContent(
  file: z.infer<typeof GistFileSchema>,
): Promise<string> {
  if (!file.truncated) return file.content;
  const res = await fetch(file.raw_url);
  if (!res.ok) throw new Error(`Failed to fetch ${file.filename}`);
  return res.text();
}

async function fetchGist(gistId: string): Promise<GistResponse> {
  const res = await fetch(`https://api.github.com/gists/${gistId}`);
  if (res.status === 404)
    throw new Error("Gist not found. Check the URL and try again.");
  if (res.status === 403 || res.status === 429)
    throw new Error(
      "GitHub API rate limit exceeded. Try again in a few minutes.",
    );
  if (!res.ok) throw new Error("Failed to fetch gist. Check your connection.");
  const json = await res.json();
  const parsed = GistResponseSchema.safeParse(json);
  if (!parsed.success) throw new Error("Unexpected gist response format.");
  return parsed.data;
}

function parseGistSessions(data: GistResponse): GistSession[] {
  const jsonlFiles = Object.values(data.files).filter((f) =>
    f.filename.endsWith(".jsonl"),
  );
  if (jsonlFiles.length === 0) {
    throw new Error(
      "No session files found in this gist. Expected .jsonl files.",
    );
  }
  return jsonlFiles.map((file) => ({
    filename: file.filename,
    result: parseSessionJsonl(file.content),
  }));
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

    const cached = getCached(gistId);
    const isStale = !cached || Date.now() - cached.ts > STALE_MS;

    // Serve from cache immediately if available
    if (cached) {
      try {
        const sessions = parseGistSessions(cached.data);
        setSessions(sessions);
        setGistUrl(cached.data.html_url);
        setError(null);
      } catch (err) {
        // Cache had no .jsonl files — fall through to fetch
      }
    }

    // Fetch from API if no cache or stale
    if (isStale) {
      if (!cached) setIsLoading(true);

      fetchGist(gistId)
        .then((data) => {
          if (cancelled) return;
          setCache(gistId, data);
          const sessions = parseGistSessions(data);
          setSessions(sessions);
          setGistUrl(data.html_url);
          setError(null);
        })
        .catch((err: Error) => {
          if (cancelled) return;
          // Only show error if we had nothing cached
          if (!cached) setError(err.message);
        })
        .finally(() => {
          if (!cancelled) setIsLoading(false);
        });
    }

    return () => {
      cancelled = true;
    };
  }, [gistId]);

  return { sessions, gistUrl, isLoading, error };
}
