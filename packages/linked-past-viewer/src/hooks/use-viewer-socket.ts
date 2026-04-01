import { useCallback, useEffect, useRef, useState } from "react";
import { getAllMessages, putMessage } from "../lib/store";
import type { ViewerMessage } from "../lib/types";

export function useViewerSocket() {
  const [messages, setMessages] = useState<ViewerMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const seenSeqs = useRef(new Set<number>());

  // Restore from IndexedDB on mount
  useEffect(() => {
    getAllMessages().then((stored) => {
      if (stored.length > 0) {
        stored.sort((a, b) => a.seq - b.seq);
        for (const msg of stored) seenSeqs.current.add(msg.seq);
        setMessages(stored);
      }
    });
  }, []);

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
        const msg = JSON.parse(e.data) as ViewerMessage;
        // Deduplicate: server replays history on reconnect, IndexedDB has prior messages
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

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return { messages, isConnected };
}
