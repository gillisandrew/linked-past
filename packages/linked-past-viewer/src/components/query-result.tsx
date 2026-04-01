import type { QueryData } from "../lib/types";
import { EntityUri } from "./entity-uri";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function isUri(value: string): boolean {
  return value.startsWith("http://") || value.startsWith("https://");
}

export function QueryResult({ data }: { data: QueryData }) {
  return (
    <div>
      {data.sparql && (
        <details className="mb-2">
          <summary className="text-xs text-muted-foreground font-semibold cursor-pointer">
            SPARQL
          </summary>
          <pre className="mt-1 p-2 rounded bg-muted text-xs overflow-x-auto whitespace-pre-wrap">
            {data.sparql}
          </pre>
        </details>
      )}
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
                  {data.columns.map((col) => (
                    <TableCell key={col} className="max-w-[300px] truncate">
                      {isUri(row[col] ?? "") ? (
                        <EntityUri uri={row[col]} />
                      ) : (
                        row[col]
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p className="text-xs text-muted-foreground mt-1">
            {data.row_count} row{data.row_count !== 1 ? "s" : ""}
          </p>
        </>
      )}
    </div>
  );
}
