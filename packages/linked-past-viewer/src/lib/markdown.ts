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
 * Format a message header line with sequence number, type, dataset, and timestamp.
 */
function formatHeader(msg: ViewerMessage): string {
  const ts = new Date(msg.timestamp).toLocaleTimeString();
  const parts = [`### #${msg.seq} ${msg.type.toUpperCase()}`];
  if (msg.dataset) parts[0] += ` [${msg.dataset}]`;
  parts[0] += ` — ${ts}`;
  return parts[0];
}

/**
 * Serialize a single viewer message to markdown.
 */
export function messageToMarkdown(msg: ViewerMessage): string {
  const header = formatHeader(msg);

  switch (msg.type) {
    case "query": {
      const parts = [header];
      if (msg.data.title) {
        parts.push(`**${msg.data.title}**`);
      }
      if (msg.data.sparql) {
        parts.push("```sparql", msg.data.sparql, "```");
      }
      parts.push(rowsToMarkdown(msg.data.columns, msg.data.rows));
      parts.push(`_${msg.data.row_count} row${msg.data.row_count !== 1 ? "s" : ""}_`);
      return parts.join("\n\n");
    }
    case "entity": {
      const meta: string[] = [];
      if (msg.data.dataset) meta.push(`Dataset: ${msg.data.dataset}`);
      if (msg.data.type_hierarchy?.length) meta.push(`Type: ${msg.data.type_hierarchy.join(" › ")}`);
      const metaLine = meta.length ? `\n${meta.join(" · ")}` : "";

      const props = msg.data.properties
        .slice(0, 10)
        .map((p) => {
          const pred = p.pred.split("/").pop()?.split("#").pop() ?? p.pred;
          return `- **${pred}:** ${p.obj}`;
        })
        .join("\n");

      const xrefs = msg.data.xrefs.length
        ? `\n\n_${msg.data.xrefs.length} cross-reference${msg.data.xrefs.length !== 1 ? "s" : ""}_`
        : "";

      return `${header}\n\n**${msg.data.name}** \`${msg.data.uri}\`${metaLine}\n\n${props}${xrefs}`;
    }
    case "links": {
      const links = msg.data.links
        .map((l) => `- ${l.confidence} | ${l.relationship} → \`${l.target}\``)
        .join("\n");
      return `${header}\n\nSource: \`${msg.data.uri}\`\n\n${links || "_No links_"}`;
    }
    case "search": {
      const results = msg.data.results
        .map((r) => `- **${r.label}** \`${r.uri}\` (${r.dataset})`)
        .join("\n");
      const count = msg.data.results.length;
      return `${header}\n\nQuery: "${msg.data.query_text}" — ${count} result${count !== 1 ? "s" : ""}\n\n${results || "_No results_"}`;
    }
    case "report": {
      const title = msg.data.title ? `**${msg.data.title}**\n\n` : "";
      return `${header}\n\n${title}${msg.data.markdown}`;
    }
  }
}
