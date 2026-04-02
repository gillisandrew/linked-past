import { useState } from "react";
import { useAnnotations } from "../hooks/use-annotations";
import { useViewerSocket } from "../hooks/use-viewer-socket";
import type { ViewerMessage } from "../lib/types";
import { ConnectionStatus } from "./connection-status";
import { Feed } from "./feed";
import { applyFilters, emptyFilters, FeedFilters, type Filters } from "./feed-filters";
import { SessionPicker } from "./session-picker";
import { AutoScrollButton, DarkModeToggle, ExpandCollapseButtons, ExportButton } from "./toolbar-actions";

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

  const isViewingPast = pastSession !== null;
  const activeMessages = isViewingPast ? pastSession.messages : liveMessages;
  const filtered = applyFilters(activeMessages, filters, bookmarks);

  function handleLoadSession(messages: ViewerMessage[], sessionId: string) {
    setPastSession({ id: sessionId, messages });
    setFilters(emptyFilters());
  }

  function handleBackToLive() {
    setPastSession(null);
    setFilters(emptyFilters());
  }

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
      <main className="max-w-6xl mx-auto px-8 py-6">
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
