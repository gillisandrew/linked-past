import { createFileRoute, Link } from "@tanstack/react-router";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import { getSourcesIndex } from "#/lib/data";
import type { SourceIndex } from "#/lib/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "#/components/ui/table";

export const Route = createFileRoute("/sources/")({
  loader: () => {
    const sources = getSourcesIndex();
    return sources.sort((a, b) => a.abbreviation.localeCompare(b.abbreviation));
  },
  head: () => ({
    meta: [
      { title: "Sources \u2014 Liber Amicorum" },
      {
        name: "description",
        content:
          "Browse secondary sources referenced in the Digital Prosopography of the Roman Republic.",
      },
    ],
  }),
  component: SourcesIndex,
});

const columnHelper = createColumnHelper<SourceIndex>();

const columns = [
  columnHelper.accessor("abbreviation", {
    header: "Abbreviation",
    cell: (info) => (
      <Link
        to="/sources/$sourceId"
        params={{ sourceId: info.row.original.id }}
        className="text-link hover:text-link-light underline decoration-link/30 hover:decoration-link"
      >
        {info.getValue()}
      </Link>
    ),
  }),
  columnHelper.accessor("name", {
    header: "Full Name",
    cell: (info) => info.getValue() ?? "\u2014",
  }),
  columnHelper.accessor("citationCount", {
    header: "Citations",
    cell: (info) => info.getValue(),
  }),
];

function SourcesIndex() {
  const sources = Route.useLoaderData();
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data: sources,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
  });

  return (
    <div className="mx-auto px-6 py-10 space-y-6">
      <div>
        <h1 className="font-heading text-3xl font-bold">Sources</h1>
        <p className="mt-1 text-ink-muted">
          {sources.length} secondary sources, sorted by abbreviation.
        </p>
      </div>
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHead
                  key={header.id}
                  className={header.column.getCanSort() ? "cursor-pointer select-none" : ""}
                  onClick={header.column.getToggleSortingHandler()}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  {{ asc: " \u2191", desc: " \u2193" }[header.column.getIsSorted() as string] ?? ""}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <TableCell key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
