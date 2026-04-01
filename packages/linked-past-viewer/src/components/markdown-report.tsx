import type { ComponentPropsWithoutRef } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ReportData } from "../lib/types";
import { datasetForUri } from "../lib/uri";
import { EntityUri } from "./entity-uri";

/**
 * Custom link renderer: if the href points to a known dataset entity,
 * render an EntityUri with popover. Otherwise render a normal external link.
 */
function MarkdownLink({ href, children }: ComponentPropsWithoutRef<"a">) {
  if (href && datasetForUri(href)) {
    const display = typeof children === "string" ? children : undefined;
    return <EntityUri uri={href} display={display} />;
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary underline"
    >
      {children}
    </a>
  );
}

export function MarkdownReport({ data }: { data: ReportData }) {
  return (
    <div>
      {data.title && <h2 className="text-lg font-semibold mb-2">{data.title}</h2>}
      <div className="prose prose-sm dark:prose-invert max-w-none">
        <Markdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: MarkdownLink,
            table: ({ children }) => (
              <table className="w-full border-collapse text-sm">{children}</table>
            ),
            th: ({ children }) => (
              <th className="text-left p-1.5 border-b-2 font-semibold bg-muted/50">{children}</th>
            ),
            td: ({ children }) => (
              <td className="p-1.5 border-b">{children}</td>
            ),
          }}
        >
          {data.markdown}
        </Markdown>
      </div>
    </div>
  );
}
