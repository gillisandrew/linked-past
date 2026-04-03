import { useMemo } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { rowsToMarkdown } from "../lib/markdown";
import type { QueryData } from "../lib/types";
import { expandPrefixedUri, isEntityUri } from "../lib/uri";
import { CopyButton } from "./copy-button";
import { DataTable } from "./data-table";
import { EntityUri } from "./entity-uri";
import { SparqlBlock } from "./sparql-block";

type Row = Record<string, string | number | null>;

function CellValue({
  value,
  prefixMap,
}: {
  value: string;
  prefixMap: Record<string, string>;
}) {
  if (isEntityUri(value)) {
    return (
      <EntityUri uri={expandPrefixedUri(value, prefixMap)} display={value} />
    );
  }

  return <span className="truncate block">{value}</span>;
}

export function QueryResult({ data }: { data: QueryData }) {
  const prefixMap = data.prefix_map ?? {};

  const columns = useMemo<ColumnDef<Row>[]>(
    () =>
      data.columns.map((col) => ({
        accessorKey: col,
        header: col,
        cell: ({ getValue }) => {
          const val = String(getValue() ?? "");
          return <CellValue value={val} prefixMap={prefixMap} />;
        },
        sortingFn: "alphanumeric",
        size: 180,
        minSize: 80,
      })),
    [data.columns, prefixMap],
  );

  return (
    <div>
      {data.sparql && <SparqlBlock sparql={data.sparql} />}
      <DataTable
        columns={columns}
        data={data.rows}
        footer={
          <div className="flex items-center gap-3 mt-1">
            <p className="text-xs text-muted-foreground">
              {data.row_count} row{data.row_count !== 1 ? "s" : ""}
            </p>
            <CopyButton
              text={rowsToMarkdown(data.columns, data.rows)}
              label="Copy as Markdown"
            />
          </div>
        }
      />
    </div>
  );
}
