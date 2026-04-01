import { useState } from "react";
import { useAnnotations } from "../hooks/use-annotations";
import { useViewerSocket } from "../hooks/use-viewer-socket";
import { ConnectionStatus } from "./connection-status";
import { Feed } from "./feed";
import { applyFilters, emptyFilters, FeedFilters, type Filters } from "./feed-filters";

export function ViewerLayout() {
  const { messages, isConnected } = useViewerSocket();
  const { bookmarks, notes, toggleBookmark, updateNote } = useAnnotations();
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const filtered = applyFilters(messages, filters, bookmarks);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur px-4 py-2 flex flex-col gap-1.5">
        <div className="flex items-center text-sm">
          <span className="font-semibold">linked-past viewer</span>
          <span className="ml-auto text-muted-foreground text-xs tabular-nums">
            {filtered.length}/{messages.length}
          </span>
          <span className="ml-3">
            <ConnectionStatus connected={isConnected} />
          </span>
        </div>
        {messages.length > 0 && (
          <FeedFilters
            messages={messages}
            filters={filters}
            bookmarkCount={bookmarks.size}
            onChange={setFilters}
          />
        )}
      </header>
      <main className="max-w-4xl mx-auto p-4">
        <Feed
          messages={filtered}
          bookmarks={bookmarks}
          notes={notes}
          onToggleBookmark={toggleBookmark}
          onUpdateNote={updateNote}
        />
      </main>
    </div>
  );
}
