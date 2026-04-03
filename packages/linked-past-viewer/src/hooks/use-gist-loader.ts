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

async function fetchFileContent(file: z.infer<typeof GistFileSchema>): Promise<string> {
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
