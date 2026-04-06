import { ViewerMessageSchema, SessionMetaSchema, EntityCacheMessageSchema } from "./schemas";
import type { ViewerMessage, EntityData } from "./schemas";

export type ParseError = {
  line: number;
  raw: string;
  error: string;
};

export type ParseResult = {
  messages: ViewerMessage[];
  errors: ParseError[];
  formatVersion: number | null;
  entityCache: Map<string, EntityData>;
};

export function parseSessionJsonl(text: string): ParseResult {
  const lines = text.split("\n").filter((l) => l.trim());
  const messages: ViewerMessage[] = [];
  const errors: ParseError[] = [];
  let formatVersion: number | null = null;
  const entityCache = new Map<string, EntityData>();

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      errors.push({ line: i + 1, raw, error: `Invalid JSON: ${e}` });
      continue;
    }

    // Session meta preamble
    const metaResult = SessionMetaSchema.safeParse(parsed);
    if (metaResult.success) {
      formatVersion = metaResult.data.format_version;
      continue;
    }

    // Entity cache messages
    const cacheResult = EntityCacheMessageSchema.safeParse(parsed);
    if (cacheResult.success) {
      for (const [uri, data] of Object.entries(cacheResult.data.data.entities)) {
        entityCache.set(uri, data);
      }
      continue;
    }

    // Regular viewer messages
    const msgResult = ViewerMessageSchema.safeParse(parsed);
    if (msgResult.success) {
      messages.push(msgResult.data);
    } else {
      errors.push({
        line: i + 1,
        raw: raw.length > 200 ? raw.slice(0, 200) + "…" : raw,
        error: msgResult.error.issues.map((e) => e.message).join("; "),
      });
    }
  }

  messages.sort((a, b) => a.seq - b.seq);
  return { messages, errors, formatVersion, entityCache };
}
