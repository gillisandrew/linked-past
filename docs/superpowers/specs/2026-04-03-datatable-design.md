# DataTable for Query Results

**Date:** 2026-04-03
**Status:** Draft
**Package:** `packages/linked-past-viewer`

## Purpose

Replace the basic HTML table in `QueryResult` with a TanStack Table-powered DataTable. Adds column sorting, resizing, and visibility toggling while preserving the existing entity URI pill rendering and expandable cell behavior.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Library | `@tanstack/react-table` | shadcn DataTable pattern, headless, React 19 compatible |
| Pagination | None | Result sets are small enough to render all rows |
| Filtering | None (MVP) | Sorting and column visibility are the priority |
| Cell rendering | Custom per-cell | Entity URIs render as `EntityUri` pills, long values get expand/collapse |
| Component split | Generic `DataTable` + query-specific column defs | DataTable is reusable for future tables |

## Features

- **Column sorting** — click column header to cycle asc → desc → none. Sorts on the raw string value.
- **Column resizing** — drag column header borders to resize.
- **Column visibility** — dropdown toggle to show/hide columns. Useful for wide SPARQL results.
- **Custom cell rendering** — entity URI values render as `EntityUri` colored pills. Values longer than 40 characters get an expandable "more/less" toggle.

## What Stays the Same

- `SparqlBlock` rendered above the table
- Row count + "Copy as Markdown" rendered below the table
- `QueryResult` component signature: `{ data: QueryData }`
- All existing styling (shadcn Table primitives)

## File Changes

**New dependency:**
- `@tanstack/react-table`

**Create:**
- `src/components/data-table.tsx` — Generic DataTable component wrapping TanStack Table with shadcn Table primitives. Accepts `columns` and `data` props. Handles sorting, resizing, and column visibility UI. Not query-specific.

**Modify:**
- `src/components/query-result.tsx` — Build TanStack `ColumnDef[]` dynamically from `data.columns`. Each column gets a custom cell renderer that checks `isEntityUri` and renders `EntityUri` or plain text with expand/collapse. Pass columns + rows to `DataTable`.

**Remove:**
- `ExpandableCell` component (logic moves into column cell renderer)

## DataTable Component Interface

```typescript
interface DataTableProps<TData> {
  columns: ColumnDef<TData, unknown>[];
  data: TData[];
}
```

Renders:
- Column visibility dropdown (top-right)
- Table with sortable headers (sort indicator icons)
- Resizable column borders
- All rows (no pagination)
