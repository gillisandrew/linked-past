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

      {session.formatVersion !== null &&
        session.formatVersion > CURRENT_FORMAT_VERSION && (
          <div className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-700 dark:text-amber-400 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            This session was created with a newer format (v{session.formatVersion}).
            Some items may not render correctly.
          </div>
        )}

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
