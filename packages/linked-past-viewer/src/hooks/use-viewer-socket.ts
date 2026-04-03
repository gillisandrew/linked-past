import { useCallback, useEffect, useRef, useState } from "react";
import { ViewerMessageSchema } from "../lib/schemas";
import { clearMessages, getAllMessages, putMessage } from "../lib/store";
import type { ViewerMessage } from "../lib/types";

export function useViewerSocket() {
  const [messages, setMessages] = useState<ViewerMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const seenSeqs = useRef(new Set<number>());
  const currentSessionId = useRef<string | null>(null);

  const connect = useCallback(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/viewer/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      backoffRef.current = 1000;
    };

    ws.onmessage = (e) => {
      try {
        const parsed = ViewerMessageSchema.safeParse(JSON.parse(e.data));
        if (!parsed.success) {
          console.warn("Invalid viewer message:", parsed.error.issues[0]?.message);
          return;
        }
        const msg = parsed.data;

        // Detect new session by session_id change
        if (msg.session_id && msg.session_id !== currentSessionId.current) {
          if (currentSessionId.current !== null) {
            // Session changed — clear old data
            seenSeqs.current.clear();
            setMessages([]);
            clearMessages();
          }
          currentSessionId.current = msg.session_id;
        }

        if (seenSeqs.current.has(msg.seq)) return;
        seenSeqs.current.add(msg.seq);
        setMessages((prev) => [...prev, msg]);
        putMessage(msg);
      } catch {
        console.warn("Failed to parse viewer message:", e.data);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      wsRef.current = null;
      const delay = Math.min(backoffRef.current, 30000);
      backoffRef.current *= 2;
      setTimeout(connect, delay);
    };
  }, []);

  // Restore from IndexedDB first, THEN connect WebSocket
  useEffect(() => {
    getAllMessages().then((stored) => {
      if (stored.length > 0) {
        stored.sort((a, b) => a.seq - b.seq);
        for (const msg of stored) seenSeqs.current.add(msg.seq);
        if (stored[0].session_id) currentSessionId.current = stored[0].session_id;
        setMessages(stored);
      }
      connect();
    });

    return () => {
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { messages, isConnected };
}
