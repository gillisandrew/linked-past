/**
 * IndexedDB persistence for viewer messages, bookmarks, and notes.
 * Uses the `idb` library for typed async access.
 *
 * Schema:
 *   messages: { seq (key), type, dataset, timestamp, data }
 *   bookmarks: { seq (key) }
 *   notes: { seq (key), text }
 */

import { openDB, type DBSchema, type IDBPDatabase } from "idb";
import type { ViewerMessage } from "./types";

interface ViewerDB extends DBSchema {
  messages: {
    key: number;
    value: ViewerMessage;
    indexes: { "by-type": string; "by-dataset": string };
  };
  bookmarks: {
    key: number;
    value: { seq: number };
  };
  notes: {
    key: number;
    value: { seq: number; text: string };
  };
}

let dbPromise: Promise<IDBPDatabase<ViewerDB>> | null = null;

function getDB(): Promise<IDBPDatabase<ViewerDB>> {
  if (!dbPromise) {
    dbPromise = openDB<ViewerDB>("linked-past-viewer", 1, {
      upgrade(db) {
        const msgStore = db.createObjectStore("messages", { keyPath: "seq" });
        msgStore.createIndex("by-type", "type");
        msgStore.createIndex("by-dataset", "dataset");
        db.createObjectStore("bookmarks", { keyPath: "seq" });
        db.createObjectStore("notes", { keyPath: "seq" });
      },
    });
  }
  return dbPromise;
}

// ── Messages ──────────────────────────────────────────────────────────────────

export async function putMessage(msg: ViewerMessage): Promise<void> {
  const db = await getDB();
  await db.put("messages", msg);
}

export async function getAllMessages(): Promise<ViewerMessage[]> {
  const db = await getDB();
  return db.getAll("messages");
}

export async function clearMessages(): Promise<void> {
  const db = await getDB();
  await db.clear("messages");
  await db.clear("bookmarks");
  await db.clear("notes");
}

// ── Bookmarks ─────────────────────────────────────────────────────────────────

export async function setBookmark(seq: number): Promise<void> {
  const db = await getDB();
  await db.put("bookmarks", { seq });
}

export async function removeBookmark(seq: number): Promise<void> {
  const db = await getDB();
  await db.delete("bookmarks", seq);
}

export async function getAllBookmarks(): Promise<Set<number>> {
  const db = await getDB();
  const all = await db.getAll("bookmarks");
  return new Set(all.map((b) => b.seq));
}

// ── Notes ─────────────────────────────────────────────────────────────────────

export async function setNote(seq: number, text: string): Promise<void> {
  const db = await getDB();
  if (text.trim()) {
    await db.put("notes", { seq, text });
  } else {
    await db.delete("notes", seq);
  }
}

export async function getAllNotes(): Promise<Map<number, string>> {
  const db = await getDB();
  const all = await db.getAll("notes");
  return new Map(all.map((n) => [n.seq, n.text]));
}
