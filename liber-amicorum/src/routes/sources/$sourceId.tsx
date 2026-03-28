import { Link, createFileRoute, notFound } from "@tanstack/react-router";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import { getSourceById } from "#/lib/data";
import type { SourceCitation } from "#/lib/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "#/components/ui/table";

export const Route = createFileRoute("/sources/$sourceId")({
  loader: async ({ params }) => {
    const source = await getSourceById(params.sourceId);
    if (!source) throw notFound();
    return source;
  },
  component: SourcePage,
  head: ({ loaderData }) => ({
    meta: [
      { title: `${loaderData?.abbreviation ?? "Source"} \u2014 Liber Amicorum` },
      {
        name: "description",
        content: loaderData
          ? `${loaderData.abbreviation}${loaderData.name ? ` \u2014 ${loaderData.name}` : ""} \u2014 ${loaderData.citations.length} citations`
          : "",
      },
    ],
  }),
});

const columnHelper = createColumnHelper<SourceCitation>();

const columns = [
  columnHelper.accessor("personName", {
    header: "Person",
    cell: (info) => {
      const row = info.row.original;
      return (
        <Link
          to="/persons/$personId"
          params={{ personId: row.personId }}
          hash={row.anchor}
          className="text-link hover:text-link-light underline decoration-link/30 hover:decoration-link"
        >
          {info.getValue()}
        </Link>
      );
    },
  }),
  columnHelper.accessor("context", {
    header: "Context",
    cell: (info) => <span className="text-sm text-ink-muted">{info.getValue()}</span>,
  }),
];

function SourcePage() {
  const source = Route.useLoaderData();
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data: source.citations,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
  });

  return (
    <div className="mx-auto px-6 py-10 space-y-8">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="font-heading text-3xl font-bold">{source.abbreviation}</h1>
        <div className="space-y-1 text-sm text-ink-muted">
          {source.name && <p>{source.name}</p>}
          {source.biblio && <p className="italic">{source.biblio}</p>}
          <p>
            {source.citations.length} citation{source.citations.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      {/* Methodological notes */}
      {source.notes.length > 0 && (
        <section className="rounded-lg border border-uncertain/30 bg-uncertain/5 p-4 space-y-2">
          <h2 className="text-sm font-semibold text-ink">Methodological Notes</h2>
          {source.notes.map((note, i) => (
            <p key={i} className="text-sm leading-relaxed text-ink/80">{note}</p>
          ))}
        </section>
      )}

      {/* Citations table */}
      {source.citations.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-heading text-xl font-semibold">Citations</h2>
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
                      {{ asc: " \u2191", desc: " \u2193" }[header.column.getIsSorted() as string] ??
                        ""}
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
        </section>
      )}
    </div>
  );
}
