import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import type { Relationship } from "#/lib/types";
import { PersonLink } from "#/components/person-link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "#/components/ui/table";

const columnHelper = createColumnHelper<Relationship>();

const columns = [
  columnHelper.accessor("type", {
    header: "Type",
    cell: (info) => <span className="text-xs uppercase text-ink-muted">{info.getValue()}</span>,
  }),
  columnHelper.display({
    id: "person",
    header: "Person",
    cell: ({ row }) => {
      const rel = row.original;
      if (rel.relatedPersonId && rel.relatedPersonName) {
        return <PersonLink id={rel.relatedPersonId} name={rel.relatedPersonName} />;
      }
      return <span className="text-sm text-ink-muted">{rel.relatedPersonName ?? "Unknown"}</span>;
    },
  }),
];

interface RelationshipsTableProps {
  data: Relationship[];
}

export function RelationshipsTable({ data }: RelationshipsTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
  });

  return (
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
  );
}
