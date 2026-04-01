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

export function Feed({ messages }: { messages: ViewerMessage[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

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
          key={`${msg.timestamp}-${i}`}
          message={msg}
          defaultOpen={i === messages.length - 1}
          subtitle={msg.type === "report" ? (msg.data.title ?? undefined) : undefined}
        >
          <MessageBody message={msg} />
        </FeedItem>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
