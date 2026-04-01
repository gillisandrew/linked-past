export type QueryData = {
  rows: Record<string, string>[];
  columns: string[];
  sparql: string;
  row_count: number;
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

export type ViewerMessage =
  | { type: "query"; dataset: string | null; timestamp: string; data: QueryData }
  | { type: "entity"; dataset: string | null; timestamp: string; data: EntityData }
  | { type: "links"; dataset: string | null; timestamp: string; data: LinksData }
  | { type: "search"; dataset: string | null; timestamp: string; data: SearchData }
  | { type: "report"; dataset: string | null; timestamp: string; data: ReportData };
