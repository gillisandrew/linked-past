import { FileDown } from "lucide-react";
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
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur px-4 py-2 flex flex-col gap-1.5">
        <div className="flex items-center gap-3 text-sm">
          <span className="font-semibold">linked-past viewer</span>
          {isViewingPast && (
            <span className="px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-700 dark:text-yellow-400 text-[11px] font-medium">
              viewing past session
            </span>
          )}
          <span className="ml-auto flex items-center gap-3">
            {activeMessages.length > 0 && (
              <ExpandCollapseButtons
                onExpandAll={() => setForceOpen((prev) => ({ value: true, rev: (prev?.rev ?? 0) + 1 }))}
                onCollapseAll={() => setForceOpen((prev) => ({ value: false, rev: (prev?.rev ?? 0) + 1 }))}
              />
            )}
            <AutoScrollButton
              active={autoScroll}
              onClick={() => setAutoScroll((prev) => !prev)}
            />
            <ExportButton messages={filtered} notes={notes} />
            <Button
              variant="ghost"
              size="icon-xs"
              title="Export session as JSONL (for sharing)"
              disabled={!liveSessionId && !pastSession}
              onClick={handleExportJsonl}
            >
              <FileDown className="h-3.5 w-3.5" />
            </Button>
            <DarkModeToggle />
            <span className="text-muted-foreground text-xs tabular-nums">
              {filtered.length}/{activeMessages.length}
            </span>
            <ConnectionStatus connected={isConnected} />
          </span>
        </div>
        <div className="flex items-center gap-4 flex-wrap">
          <SessionPicker
            onLoadSession={handleLoadSession}
            onBackToLive={handleBackToLive}
            viewingSessionId={isViewingPast ? pastSession.id : null}
            initialSessionId={initialSessionId}
          />
          {activeMessages.length > 0 && (
            <FeedFilters
              messages={activeMessages}
              filters={filters}
              bookmarkCount={bookmarks.size}
              onChange={setFilters}
            />
          )}
        </div>
      </header>
      <main className="px-4 py-6">
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
