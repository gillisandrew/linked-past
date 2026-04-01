import { useCallback, useEffect, useState } from "react";
import {
  getAllBookmarks,
  getAllNotes,
  removeBookmark,
  setBookmark,
  setNote as persistNote,
} from "../lib/store";

/**
 * Manages bookmarks (pinned items) and notes, synced to IndexedDB.
 */
export function useAnnotations() {
  const [bookmarks, setBookmarks] = useState<Set<number>>(new Set());
  const [notes, setNotes] = useState<Map<number, string>>(new Map());

  // Restore from IndexedDB on mount
  useEffect(() => {
    getAllBookmarks().then(setBookmarks);
    getAllNotes().then(setNotes);
  }, []);

  const toggleBookmark = useCallback(
    (seq: number) => {
      setBookmarks((prev) => {
        const next = new Set(prev);
        if (next.has(seq)) {
          next.delete(seq);
          removeBookmark(seq);
        } else {
          next.add(seq);
          setBookmark(seq);
        }
        return next;
      });
    },
    [],
  );

  const updateNote = useCallback(
    (seq: number, text: string) => {
      setNotes((prev) => {
        const next = new Map(prev);
        if (text.trim()) {
          next.set(seq, text);
        } else {
          next.delete(seq);
        }
        persistNote(seq, text);
        return next;
      });
    },
    [],
  );

  return { bookmarks, notes, toggleBookmark, updateNote };
}
