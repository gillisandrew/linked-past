import { z } from "zod";

// --- Session metadata preamble ---

export const SessionMetaSchema = z.object({
  format_version: z.number().int().positive(),
  type: z.literal("session_meta"),
  session_id: z.string(),
  created_at: z.string(),
});

// --- Data schemas per message type ---

const PredicateMetaSchema = z.object({
  label: z.string().optional(),
  comment: z.string().optional(),
  domain: z.string().optional(),
  range: z.string().optional(),
});

const XrefLinkSchema = z.object({
  target: z.string(),
  relationship: z.string(),
  confidence: z.string(),
  basis: z.string(),
});

export const QueryDataSchema = z.object({
  rows: z.array(z.record(z.string(), z.string())),
  columns: z.array(z.string()),
  sparql: z.string(),
  row_count: z.number(),
  prefix_map: z.record(z.string(), z.string()).optional(),
  title: z.string().nullish(),
});

export const EntityDataSchema = z.object({
  uri: z.string(),
  name: z.string(),
  dataset: z.string().nullable(),
  description: z.string().optional(),
  type_hierarchy: z.array(z.string()).optional(),
  see_also: z.array(z.string()).optional(),
  properties: z.array(z.object({ pred: z.string(), obj: z.string() })),
  predicate_meta: z.record(z.string(), PredicateMetaSchema).optional(),
  xrefs: z.array(XrefLinkSchema),
});

export const LinksDataSchema = z.object({
  uri: z.string(),
  links: z.array(XrefLinkSchema),
});

export const SearchDataSchema = z.object({
  query_text: z.string(),
  results: z.array(
    z.object({ uri: z.string(), label: z.string(), dataset: z.string() }),
  ),
});

export const ReportDataSchema = z.object({
  title: z.string().nullable(),
  markdown: z.string(),
});

// --- Base message fields ---

const BaseMessageFields = {
  session_id: z.string(),
  seq: z.number(),
  dataset: z.string().nullable(),
  timestamp: z.string(),
};

// --- Discriminated union ---

export const ViewerMessageSchema = z.discriminatedUnion("type", [
  z.object({ ...BaseMessageFields, type: z.literal("query"), data: QueryDataSchema }),
  z.object({ ...BaseMessageFields, type: z.literal("entity"), data: EntityDataSchema }),
  z.object({ ...BaseMessageFields, type: z.literal("links"), data: LinksDataSchema }),
  z.object({ ...BaseMessageFields, type: z.literal("search"), data: SearchDataSchema }),
  z.object({ ...BaseMessageFields, type: z.literal("report"), data: ReportDataSchema }),
]);

// --- Inferred types ---

export type SessionMeta = z.infer<typeof SessionMetaSchema>;
export type ViewerMessage = z.infer<typeof ViewerMessageSchema>;
export type QueryData = z.infer<typeof QueryDataSchema>;
export type EntityData = z.infer<typeof EntityDataSchema>;
export type LinksData = z.infer<typeof LinksDataSchema>;
export type SearchData = z.infer<typeof SearchDataSchema>;
export type ReportData = z.infer<typeof ReportDataSchema>;
export type XrefLink = z.infer<typeof XrefLinkSchema>;
export type PredicateMeta = z.infer<typeof PredicateMetaSchema>;
