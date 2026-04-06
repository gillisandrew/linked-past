import { FileDown, SlidersHorizontal } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAnnotations } from "../hooks/use-annotations";
import { useViewerSocket } from "../hooks/use-viewer-socket";
import { downloadSessionJsonl } from "../lib/download";
import type { ViewerMessage } from "../lib/types";
import { Button } from "./ui/button";
import { ConnectionStatus } from "./connection-status";
import { Feed } from "./feed";
import { applyFilters, emptyFilters, FeedFilters, type Filters } from "./feed-filters";
import { SessionPicker } from "./session-picker";
import { AutoScrollButton, DarkModeToggle, ExpandCollapseButtons, ExportButton } from "./toolbar-actions";

/**
 * Read ?session= from the current URL.
 */
function getSessionFromUrl(): string | null {
  const params = new URLSearchParams(window.location.search);
  return params.get("session");
}

/**
 * Update ?session= in the URL without a full page reload.
 */
function setSessionInUrl(sessionId: string | null) {
  const url = new URL(window.location.href);
  if (sessionId) {
    url.searchParams.set("session", sessionId);
  } else {
    url.searchParams.delete("session");
  }
  window.history.replaceState({}, "", url.toString());
}

export function ViewerLayout() {
  const { messages: liveMessages, isConnected } = useViewerSocket();
  const { bookmarks, notes, toggleBookmark, updateNote } = useAnnotations();
  const [filters, setFilters] = useState<Filters>(emptyFilters);

  // Expand/collapse all: rev counter ensures repeated clicks re-trigger the effect
  const [forceOpen, setForceOpen] = useState<{ value: boolean; rev: number } | null>(null);
  const [autoScroll, setAutoScroll] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  // Past session viewing
  const [pastSession, setPastSession] = useState<{
    id: string;
    messages: ViewerMessage[];
  } | null>(null);

  // On mount: load session from URL param if present
  const [initialSessionId] = useState(getSessionFromUrl);

  const isViewingPast = pastSession !== null;
  const activeMessages = isViewingPast ? pastSession.messages : liveMessages;
  const filtered = applyFilters(activeMessages, filters, bookmarks);

  const liveSessionId = useMemo(
    () => (liveMessages.length > 0 ? liveMessages[0].session_id : null),
    [liveMessages],
  );

  const handleExportJsonl = useCallback(() => {
    const sessionId = pastSession?.id ?? liveSessionId;
    if (sessionId) downloadSessionJsonl(sessionId);
  }, [pastSession, liveSessionId]);

  function handleLoadSession(messages: ViewerMessage[], sessionId: string) {
    setPastSession({ id: sessionId, messages });
    setFilters(emptyFilters());
    setSessionInUrl(sessionId);
  }

  function handleBackToLive() {
    setPastSession(null);
    setFilters(emptyFilters());
    setSessionInUrl(null);
  }

  // Handle browser back/forward
  useEffect(() => {
    function onPopState() {
      const sessionId = getSessionFromUrl();
      if (!sessionId) {
        setPastSession(null);
        setFilters(emptyFilters());
      }
      // If there's a session ID in the URL after popstate, the SessionPicker
      // will handle loading it via the initialSessionId mechanism
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b border-border bg-background">
        <div className="flex items-center gap-3 px-5 h-10 text-sm">
          <span className="text-[13px] font-semibold uppercase tracking-wide">
            linked-past
          </span>
          <ConnectionStatus connected={isConnected} />
          {isViewingPast && (
            <span className="text-[11px] text-yellow-600 dark:text-yellow-400 font-medium">
              past session
            </span>
          )}
          <span className="ml-auto flex items-center gap-3">
            <SessionPicker
              onLoadSession={handleLoadSession}
              onBackToLive={handleBackToLive}
              viewingSessionId={isViewingPast ? pastSession.id : null}
              initialSessionId={initialSessionId}
            />
            {activeMessages.length > 0 && (
              <button
                onClick={() => setShowFilters((v) => !v)}
                className={`text-muted-foreground hover:text-foreground cursor-pointer transition-colors ${showFilters ? "text-foreground" : ""}`}
                title="Toggle filters"
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
              </button>
            )}
            {activeMessages.length > 0 && (
              <ExpandCollapseButtons
                onExpandAll={() => setForceOpen((prev) => ({ value: true, rev: (prev?.rev ?? 0) + 1 }))}
                onCollapseAll={() => setForceOpen((prev) => ({ value: false, rev: (prev?.rev ?? 0) + 1 }))}
              />
            )}
            <AutoScrollButton active={autoScroll} onClick={() => setAutoScroll((prev) => !prev)} />
            <ExportButton messages={filtered} notes={notes} />
            <Button
              variant="ghost"
              size="icon-xs"
              title="Export session as JSONL"
              disabled={!liveSessionId && !pastSession}
              onClick={handleExportJsonl}
            >
              <FileDown className="h-3.5 w-3.5" />
            </Button>
            <DarkModeToggle />
            <span className="text-muted-foreground text-[11px] tabular-nums">
              {filtered.length}/{activeMessages.length}
            </span>
          </span>
        </div>
        {showFilters && activeMessages.length > 0 && (
          <div className="px-5 py-1.5 border-t border-border">
            <FeedFilters
              messages={activeMessages}
              filters={filters}
              bookmarkCount={bookmarks.size}
              onChange={setFilters}
            />
          </div>
        )}
      </header>
      <main className="px-5 py-4">
        <Feed
          messages={filtered}
          bookmarks={bookmarks}
          notes={notes}
          autoScroll={autoScroll}
          forceOpen={forceOpen}
          onToggleBookmark={isViewingPast ? undefined : toggleBookmark}
          onUpdateNote={isViewingPast ? undefined : updateNote}
        />
      </main>
    </div>
  );
}
