import { ViewerMessageSchema, SessionMetaSchema } from "./schemas";
import type { ViewerMessage } from "./schemas";

export type ParseError = {
  line: number;
  raw: string;
  error: string;
};

export type ParseResult = {
  messages: ViewerMessage[];
  errors: ParseError[];
  formatVersion: number | null;
};

export function parseSessionJsonl(text: string): ParseResult {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== "");
  const messages: ViewerMessage[] = [];
  const errors: ParseError[] = [];
  let formatVersion: number | null = null;

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const lineNum = i + 1;

    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      errors.push({
        line: lineNum,
        raw: raw.length > 200 ? raw.slice(0, 200) + "\u2026" : raw,
        error: "Invalid JSON",
      });
      continue;
    }

    // Check for session_meta preamble
    const meta = SessionMetaSchema.safeParse(parsed);
    if (meta.success) {
      formatVersion = meta.data.format_version;
      continue;
    }

    // Validate as a viewer message
    const result = ViewerMessageSchema.safeParse(parsed);
    if (result.success) {
      messages.push(result.data);
    } else {
      const firstIssue = result.error.issues[0];
      const path = firstIssue?.path.join(".") || "";
      const reason = firstIssue?.message || "Validation failed";
      errors.push({
        line: lineNum,
        raw: raw.length > 200 ? raw.slice(0, 200) + "\u2026" : raw,
        error: path ? `${path}: ${reason}` : reason,
      });
    }
  }

  messages.sort((a, b) => a.seq - b.seq);

  return { messages, errors, formatVersion };
}
