import type { ComponentPropsWithoutRef } from "react";
import Markdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import type { ReportData } from "../lib/types";
import { datasetForUri } from "../lib/uri";
import { EntityUri } from "./entity-uri";
import { MermaidBlock } from "./mermaid-block";

/**
 * Custom link renderer: if the href points to a known dataset entity,
 * render an EntityUri with popover. Otherwise render a normal external link.
 */
function MarkdownLink({ href, children }: ComponentPropsWithoutRef<"a">) {
  if (href && datasetForUri(href)) {
    const display = typeof children === "string" ? children : undefined;
    return <EntityUri uri={href} display={display} showBadge={false} />;
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

/**
 * Custom code renderer: mermaid fenced blocks become diagrams,
 * other fenced blocks get themed pre/code, inline code is left alone.
 */
function CodeBlock({
  className,
  children,
  node,
}: ComponentPropsWithoutRef<"code"> & { node?: { position?: unknown } }) {
  const lang = className?.replace("language-", "");
  const isBlock = !!lang || (typeof children === "string" && children.includes("\n"));

  if (!isBlock) {
    // Inline code — let prose styles handle it
    return <code className="bg-muted px-1 py-0.5 rounded text-[0.85em]">{children}</code>;
  }

  const code = String(children).replace(/\n$/, "");

  if (lang === "mermaid") {
    return <MermaidBlock chart={code} />;
  }

  // Block code — explicit light-mode-friendly styling
  return <code className={className}>{children}</code>;
}

export function MarkdownReport({ data }: { data: ReportData }) {
  return (
    <div className="space-y-4">
      <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:mt-4 prose-headings:mb-2 prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-pre:my-2 prose-pre:bg-muted prose-pre:text-foreground prose-pre:rounded prose-pre:p-3 prose-pre:text-xs prose-hr:my-4 prose-table:my-2">
        <Markdown
          remarkPlugins={[remarkGfm, remarkBreaks]}
          components={{
            a: MarkdownLink,
            code: CodeBlock,
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
