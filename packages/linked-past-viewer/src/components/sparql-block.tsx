import { useEffect, useState } from "react";
import type { Highlighter } from "shiki";
import { CopyButton } from "./copy-button";

let highlighterPromise: Promise<Highlighter> | null = null;

function getHighlighter() {
  if (!highlighterPromise) {
    highlighterPromise = import("shiki").then((shiki) =>
      shiki.createHighlighter({
        themes: ["github-light", "github-dark"],
        langs: ["sparql"],
      }),
    );
  }
  return highlighterPromise;
}

export function SparqlBlock({ sparql }: { sparql: string }) {
  const [html, setHtml] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getHighlighter().then((highlighter) => {
      if (cancelled) return;
      const highlighted = highlighter.codeToHtml(sparql, {
        lang: "sparql",
        themes: { light: "github-light", dark: "github-dark" },
      });
      setHtml(highlighted);
    });
    return () => {
      cancelled = true;
    };
  }, [sparql]);

  return (
    <details className="mb-2">
      <summary className="text-xs text-muted-foreground font-semibold cursor-pointer">
        SPARQL
      </summary>
      <div className="relative mt-1">
        <CopyButton text={sparql} label="Copy SPARQL" className="absolute top-1 right-1 z-10" />
        {html ? (
          <div
            className="rounded text-xs overflow-x-auto [&_pre]:p-2 [&_pre]:pr-20 [&_pre]:rounded [&_pre]:bg-muted"
            dangerouslySetInnerHTML={{ __html: html }}
          />
        ) : (
          <pre className="p-2 pr-20 rounded bg-muted text-xs overflow-x-auto whitespace-pre-wrap">
            {sparql}
          </pre>
        )}
      </div>
    </details>
  );
}
