import { useCallback, useEffect, useRef, useState } from "react";
import { clearMessages, getAllMessages, putMessage } from "../lib/store";
import type { ViewerMessage } from "../lib/types";

export function useViewerSocket() {
  const [messages, setMessages] = useState<ViewerMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const seenSeqs = useRef(new Set<number>());
  const maxSeq = useRef(0);
  const isFirstMessage = useRef(true);

  const connect = useCallback(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/viewer/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      backoffRef.current = 1000;
      isFirstMessage.current = true;
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as ViewerMessage;

        // Detect new session: first message after connect has seq <= our maxSeq
        // This means the server restarted or stop_viewer/start_viewer was called
        if (isFirstMessage.current) {
          isFirstMessage.current = false;
          if (msg.seq <= maxSeq.current && maxSeq.current > 0) {
            // New session — clear everything and start fresh
            seenSeqs.current.clear();
            maxSeq.current = 0;
            setMessages([]);
            clearMessages();
          }
        }

        if (seenSeqs.current.has(msg.seq)) return;
        seenSeqs.current.add(msg.seq);
        if (msg.seq > maxSeq.current) maxSeq.current = msg.seq;
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
        for (const msg of stored) {
          seenSeqs.current.add(msg.seq);
          if (msg.seq > maxSeq.current) maxSeq.current = msg.seq;
        }
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
