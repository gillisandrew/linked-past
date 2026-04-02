import { useState } from "react";
import { rowsToMarkdown } from "../lib/markdown";
import type { QueryData } from "../lib/types";
import { expandPrefixedUri, isEntityUri } from "../lib/uri";
import { CopyButton } from "./copy-button";
import { EntityUri } from "./entity-uri";
import { SparqlBlock } from "./sparql-block";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function ExpandableCell({ value, children }: { value: string; children: React.ReactNode }) {
  const [expanded, setExpanded] = useState(false);
  const needsTruncation = value.length > 40;

  if (!needsTruncation) {
    return <TableCell className="max-w-[300px]">{children}</TableCell>;
  }

  return (
    <TableCell className={expanded ? "whitespace-normal break-words" : "max-w-[300px] truncate"}>
      {children}
      <button
        onClick={() => setExpanded(!expanded)}
        className="ml-1 text-[10px] text-muted-foreground hover:text-foreground cursor-pointer"
      >
        {expanded ? "less" : "more"}
      </button>
    </TableCell>
  );
}

export function QueryResult({ data }: { data: QueryData }) {
  const prefixMap = data.prefix_map ?? {};

  function resolveUri(value: string): string {
    return expandPrefixedUri(value, prefixMap);
  }

  return (
    <div>
      {data.sparql && <SparqlBlock sparql={data.sparql} />}
      {data.rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No results</p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                {data.columns.map((col) => (
                  <TableHead key={col}>{col}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.rows.map((row, i) => (
                <TableRow key={i}>
                  {data.columns.map((col) => {
                    const val = row[col] ?? "";
                    return (
                      <ExpandableCell key={col} value={val}>
                        {isEntityUri(val) ? (
                          <EntityUri uri={resolveUri(val)} display={val} />
                        ) : (
                          val
                        )}
                      </ExpandableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex items-center gap-3 mt-1">
            <p className="text-xs text-muted-foreground">
              {data.row_count} row{data.row_count !== 1 ? "s" : ""}
            </p>
            <CopyButton
              text={rowsToMarkdown(data.columns, data.rows)}
              label="Copy as Markdown"
            />
          </div>
        </>
      )}
    </div>
  );
}
