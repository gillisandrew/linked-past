import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import type { SessionInfo, ViewerMessage } from "../lib/types";
import { Button } from "./ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "./ui/select";

async function fetchSessions(): Promise<SessionInfo[]> {
  const res = await fetch("/viewer/api/sessions");
  if (!res.ok) return [];
  return res.json();
}

async function fetchSession(id: string): Promise<ViewerMessage[]> {
  const res = await fetch(`/viewer/api/sessions/${id}`);
  if (!res.ok) return [];
  return res.json();
}

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatTimeRange(
  started: string | null,
  lastActivity: string | null,
): string {
  const start = formatTime(started);
  if (!lastActivity) return start;
  const end = new Date(lastActivity);
  if (isNaN(end.getTime())) return start;
  return `${start} – ${end.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`;
}

export function SessionPicker({
  onLoadSession,
  onBackToLive,
  viewingSessionId,
  initialSessionId,
}: {
  onLoadSession: (messages: ViewerMessage[], sessionId: string) => void;
  onBackToLive: () => void;
  viewingSessionId: string | null;
  initialSessionId?: string | null;
}) {
  const { data: sessions, refetch } = useQuery({
    queryKey: ["sessions"],
    queryFn: fetchSessions,
    staleTime: 10_000,
  });

  // Auto-load session from URL param on first render
  const didAutoLoad = useRef(false);
  useEffect(() => {
    if (didAutoLoad.current || !initialSessionId || !sessions) return;
    const match = sessions.find((s) => s.id === initialSessionId);
    if (match) {
      didAutoLoad.current = true;
      fetchSession(initialSessionId).then((messages) => {
        onLoadSession(messages, initialSessionId);
      });
    }
  }, [sessions, initialSessionId, onLoadSession]);

  const handleSelect = useCallback(
    async (value: string | null) => {
      if (!value || value === "__live__") {
        onBackToLive();
        return;
      }
      const messages = await fetchSession(value);
      onLoadSession(messages, value);
    },
    [onLoadSession, onBackToLive],
  );

  const handleExport = useCallback(
    async (sessionId: string, e: React.MouseEvent) => {
      e.stopPropagation();
      const res = await fetch(
        `/viewer/api/sessions/${sessionId}?format=jsonl`,
      );
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `linked-past-${sessionId}.jsonl`;
      a.click();
      URL.revokeObjectURL(url);
    },
    [],
  );

  if (!sessions || sessions.length === 0) return null;

  const currentSession = sessions.find((s) => s.is_current);
  const pastSessions = sessions.filter((s) => !s.is_current);

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted-foreground font-medium">Session:</span>
      {viewingSessionId && (
        <Button variant="default" size="xs" onClick={onBackToLive}>
          &larr; Live
        </Button>
      )}
      <Select
        value={viewingSessionId ?? "__live__"}
        onValueChange={handleSelect}
        onOpenChange={(open) => {
          if (open) refetch();
        }}
      >
        <SelectTrigger size="sm" className="min-w-[180px] text-xs">
          {viewingSessionId ? (
            <span className="flex flex-1 text-left truncate">
              {(() => {
                const s = pastSessions.find((s) => s.id === viewingSessionId);
                return s
                  ? `${formatTime(s.started)} · ${s.message_count} msgs`
                  : viewingSessionId;
              })()}
            </span>
          ) : (
            <span className="flex flex-1 items-center gap-1.5 text-left">
              {currentSession && (
                <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
              )}
              Current session
            </span>
          )}
        </SelectTrigger>
        <SelectContent align="start" alignItemWithTrigger={false} className="min-w-[320px]">
          <SelectItem value="__live__">
            <span className="flex items-center gap-1.5">
              {currentSession && (
                <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
              )}
              <span>
                Current session
                {currentSession &&
                  ` (${currentSession.message_count} msgs)`}
              </span>
            </span>
          </SelectItem>
          {pastSessions.map((s) => (
            <SelectItem key={s.id} value={s.id} className="pr-8">
              <span className="truncate">
                {formatTimeRange(s.started, s.last_activity)} &middot;{" "}
                {s.message_count} msgs
              </span>
              <button
                className="absolute right-1.5 shrink-0 text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded"
                title="Download as JSONL"
                onClick={(e) => handleExport(s.id, e)}
              >
                <Download className="h-3 w-3" />
              </button>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
