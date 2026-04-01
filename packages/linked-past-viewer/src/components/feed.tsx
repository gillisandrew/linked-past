import { useEffect, useRef } from "react";
import type { ViewerMessage } from "../lib/types";
import { EntityCard } from "./entity-card";
import { FeedItem } from "./feed-item";
import { MarkdownReport } from "./markdown-report";
import { QueryResult } from "./query-result";
import { SearchResults } from "./search-results";
import { XrefList } from "./xref-list";

function MessageBody({ message }: { message: ViewerMessage }) {
  switch (message.type) {
    case "query":
      return <QueryResult data={message.data} />;
    case "entity":
      return <EntityCard data={message.data} />;
    case "links":
      return <XrefList links={message.data.links} />;
    case "search":
      return <SearchResults data={message.data} />;
    case "report":
      return <MarkdownReport data={message.data} />;
  }
}

function getSubtitle(msg: ViewerMessage): string | undefined {
  if (msg.type === "report") return msg.data.title ?? undefined;
  if (msg.type === "query") {
    const title = msg.data.title ?? undefined;
    const count = `${msg.data.row_count} row${msg.data.row_count !== 1 ? "s" : ""}`;
    return title ? `${title} (${count})` : count;
  }
  if (msg.type === "search") {
    const n = msg.data.results.length;
    return `"${msg.data.query_text}" (${n} result${n !== 1 ? "s" : ""})`;
  }
  if (msg.type === "links") {
    const n = msg.data.links.length;
    return `${n} link${n !== 1 ? "s" : ""}`;
  }
  if (msg.type === "entity") {
    return msg.data.name;
  }
  return undefined;
}

export function Feed({
  messages,
  bookmarks,
  notes,
  autoScroll = false,
  forceOpen,
  onToggleBookmark,
  onUpdateNote,
}: {
  messages: ViewerMessage[];
  bookmarks: Set<number>;
  notes: Map<number, string>;
  autoScroll?: boolean;
  forceOpen?: { value: boolean; rev: number } | null;
  onToggleBookmark?: (seq: number) => void;
  onUpdateNote?: (seq: number, text: string) => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, autoScroll]);

  if (messages.length === 0) {
    return (
      <p className="text-muted-foreground text-center py-20">
        Waiting for results… Run a query in Claude to see results here.
      </p>
    );
  }

  return (
    <div>
      {messages.map((msg, i) => (
        <FeedItem
          key={msg.seq}
          message={msg}
          defaultOpen={i === messages.length - 1 || bookmarks.has(msg.seq)}
          forceOpen={forceOpen}
          subtitle={getSubtitle(msg)}
          bookmarked={bookmarks.has(msg.seq)}
          note={notes.get(msg.seq)}
          onToggleBookmark={onToggleBookmark ? () => onToggleBookmark(msg.seq) : undefined}
          onUpdateNote={onUpdateNote ? (text) => onUpdateNote(msg.seq, text) : undefined}
        >
          <MessageBody message={msg} />
        </FeedItem>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
