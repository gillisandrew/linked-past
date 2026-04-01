import type { ViewerMessage } from "./types";

/**
 * Convert query rows to a markdown table string.
 */
export function rowsToMarkdown(
  columns: string[],
  rows: Record<string, string>[],
): string {
  if (columns.length === 0 || rows.length === 0) return "_No results_";
  const header = `| ${columns.join(" | ")} |`;
  const sep = `| ${columns.map(() => "---").join(" | ")} |`;
  const body = rows
    .map((row) => `| ${columns.map((c) => row[c] ?? "").join(" | ")} |`)
    .join("\n");
  return `${header}\n${sep}\n${body}`;
}

/**
 * Serialize a single viewer message to markdown.
 */
export function messageToMarkdown(msg: ViewerMessage): string {
  const ts = new Date(msg.timestamp).toLocaleTimeString();
  const header = `### ${msg.type}${msg.dataset ? ` (${msg.dataset})` : ""} — ${ts}`;

  switch (msg.type) {
    case "query": {
      const parts = [header];
      if (msg.data.sparql) {
        parts.push("```sparql", msg.data.sparql, "```");
      }
      parts.push(rowsToMarkdown(msg.data.columns, msg.data.rows));
      parts.push(`_${msg.data.row_count} rows_`);
      return parts.join("\n\n");
    }
    case "entity": {
      const props = msg.data.properties
        .slice(0, 10)
        .map((p) => {
          const pred = p.pred.split("/").pop()?.split("#").pop() ?? p.pred;
          return `- **${pred}:** ${p.obj}`;
        })
        .join("\n");
      return `${header}\n\n**${msg.data.name}** \`${msg.data.uri}\`\n\n${props}`;
    }
    case "links": {
      const links = msg.data.links
        .map((l) => `- ${l.confidence} | ${l.relationship} → \`${l.target}\``)
        .join("\n");
      return `${header}\n\n${links || "_No links_"}`;
    }
    case "search": {
      const results = msg.data.results
        .map((r) => `- **${r.label}** \`${r.uri}\` (${r.dataset})`)
        .join("\n");
      return `${header}\n\nQuery: "${msg.data.query_text}"\n\n${results || "_No results_"}`;
    }
    case "report": {
      const title = msg.data.title ? `**${msg.data.title}**\n\n` : "";
      return `${header}\n\n${title}${msg.data.markdown}`;
    }
  }
}
