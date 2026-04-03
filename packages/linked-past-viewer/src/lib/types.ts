// Message types — inferred from Zod schemas (single source of truth)
export type {
  ViewerMessage,
  QueryData,
  EntityData,
  LinksData,
  SearchData,
  ReportData,
  XrefLink,
  PredicateMeta,
  SessionMeta,
} from "./schemas";

// Session list item (from /viewer/api/sessions, not part of JSONL format)
export type SessionInfo = {
  id: string;
  message_count: number;
  started: string;
  last_activity: string;
  is_current: boolean;
};
