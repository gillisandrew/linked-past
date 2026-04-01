import { useQuery } from "@tanstack/react-query";
import type { SessionInfo, ViewerMessage } from "../lib/types";

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

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function SessionPicker({
  onLoadSession,
  onBackToLive,
  viewingSessionId,
}: {
  onLoadSession: (messages: ViewerMessage[], sessionId: string) => void;
  onBackToLive: () => void;
  viewingSessionId: string | null;
}) {
  const { data: sessions, refetch } = useQuery({
    queryKey: ["sessions"],
    queryFn: fetchSessions,
    staleTime: 10_000,
  });

  async function handleSelect(id: string) {
    const messages = await fetchSession(id);
    onLoadSession(messages, id);
  }

  if (!sessions || sessions.length <= 1) return null;

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted-foreground font-medium">Session:</span>
      {viewingSessionId && (
        <button
          onClick={onBackToLive}
          className="px-2 py-0.5 rounded text-[11px] font-medium border border-primary bg-primary text-primary-foreground cursor-pointer"
        >
          ← Live
        </button>
      )}
      <select
        value={viewingSessionId ?? ""}
        onChange={(e) => {
          if (e.target.value) handleSelect(e.target.value);
          else onBackToLive();
        }}
        onFocus={() => refetch()}
        className="bg-transparent border rounded px-1.5 py-0.5 text-xs text-foreground cursor-pointer"
      >
        <option value="">Current session</option>
        {sessions
          .filter((s) => !s.is_current)
          .map((s) => (
            <option key={s.id} value={s.id}>
              {formatTime(s.started)} ({s.message_count} messages)
            </option>
          ))}
      </select>
    </div>
  );
}
