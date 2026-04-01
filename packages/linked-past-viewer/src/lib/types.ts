export type QueryData = {
  rows: Record<string, string>[];
  columns: string[];
  sparql: string;
  row_count: number;
  prefix_map?: Record<string, string>;
  title?: string | null;
};

export type EntityData = {
  uri: string;
  name: string;
  dataset: string | null;
  properties: { pred: string; obj: string }[];
  xrefs: XrefLink[];
};

export type XrefLink = {
  target: string;
  relationship: string;
  confidence: string;
  basis: string;
};

export type LinksData = {
  uri: string;
  links: XrefLink[];
};

export type SearchData = {
  query_text: string;
  results: { uri: string; label: string; dataset: string }[];
};

export type ReportData = {
  title: string | null;
  markdown: string;
};

type BaseMessage = {
  session_id: string;
  seq: number;
  dataset: string | null;
  timestamp: string;
};

export type SessionInfo = {
  id: string;
  message_count: number;
  started: string;
  last_activity: string;
  is_current: boolean;
};

export type ViewerMessage =
  | (BaseMessage & { type: "query"; data: QueryData })
  | (BaseMessage & { type: "entity"; data: EntityData })
  | (BaseMessage & { type: "links"; data: LinksData })
  | (BaseMessage & { type: "search"; data: SearchData })
  | (BaseMessage & { type: "report"; data: ReportData });
