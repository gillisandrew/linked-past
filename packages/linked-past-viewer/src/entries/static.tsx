import "@/app.css";

import { createRoot } from "react-dom/client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DropZone } from "@/components/drop-zone";
import { Feed } from "@/components/feed";
import { FeedFilters, applyFilters, emptyFilters, type Filters } from "@/components/feed-filters";
import { FormatVersionWarning, ParseErrorBanner } from "@/components/session-warnings";
import { ExpandCollapseButtons } from "@/components/toolbar-actions";
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
  AlertTriangle,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ErrorBoundary } from "@/components/error-boundary";

const CURRENT_FORMAT_VERSION = 1;
const queryClient = new QueryClient();

function getGistId(): string | null {
  const hash = window.location.hash.slice(1);
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
  const [filters, setFilters] = useState<Filters>(emptyFilters);

  useEffect(() => {
    const onHashChange = () => setGistId(getGistId());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const { loadFromParseResult, clear: clearSession } = session;

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
    setFilters(emptyFilters);
    history.replaceState(null, "", window.location.pathname + window.location.search);
  }, [clearSession]);

  if (gistId && gist.isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Loading gist…</p>
      </div>
    );
  }

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

  if (!session.isLoaded) {
    return (
      <DropZone
        onLoadText={session.loadFromText}
        onLoadFile={session.loadFromFile}
      />
    );
  }

  const isGistMode = gistId !== null && gist.sessions.length > 0;
  const filtered = useMemo(
    () => applyFilters(session.messages, filters, new Set()),
    [session.messages, filters],
  );

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
            <span className="text-xs text-muted-foreground tabular-nums">
              {filtered.length}/{session.messages.length}
            </span>
            <ExpandCollapseButtons
              onExpandAll={() =>
                setForceOpen((p) => ({ value: true, rev: (p?.rev ?? 0) + 1 }))
              }
              onCollapseAll={() =>
                setForceOpen((p) => ({ value: false, rev: (p?.rev ?? 0) + 1 }))
              }
            />
            <Button variant="ghost" size="sm" onClick={handleClearAll}>
              <FolderOpen className="h-4 w-4 mr-1" />
              Load another
            </Button>
          </div>
        </div>
        {session.messages.length > 0 && (
          <div className="px-4 py-1.5 border-t border-border/50">
            <FeedFilters
              messages={session.messages}
              filters={filters}
              bookmarkCount={0}
              onChange={setFilters}
            />
          </div>
        )}
      </header>

      <FormatVersionWarning
        formatVersion={session.formatVersion}
        currentVersion={CURRENT_FORMAT_VERSION}
      />
      <ParseErrorBanner errors={session.errors} />

      <div className="p-4">
        <Feed
          messages={filtered}
          bookmarks={new Set()}
          notes={new Map()}
          forceOpen={forceOpen}
        />
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <StaticModeProvider value={true}>
          <StaticApp />
        </StaticModeProvider>
      </TooltipProvider>
    </QueryClientProvider>
  </ErrorBoundary>,
);
