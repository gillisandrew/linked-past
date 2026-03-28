import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import type { StatusAssertion } from "#/lib/types";
import { formatYearUncertain } from "#/lib/format";
import { SourceBadge } from "#/components/source-badge";
import { UncertaintyMarker } from "#/components/uncertainty-marker";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "#/components/ui/table";

const columnHelper = createColumnHelper<StatusAssertion>();

const columns = [
  columnHelper.accessor("status", {
    header: "Status",
    cell: (info) => {
      const row = info.row.original;
      return (
        <UncertaintyMarker
          uncertain={row.uncertain}
          notes={row.notes.length > 0 ? row.notes : undefined}
        >
          {info.getValue()}
        </UncertaintyMarker>
      );
    },
  }),
  columnHelper.accessor("dateStart", {
    header: "From",
    cell: (info) => {
      const row = info.row.original;
      return (
        <UncertaintyMarker
          uncertain={row.dateStartUncertain}
          notes={row.notes.length > 0 ? row.notes : undefined}
        >
          {formatYearUncertain(info.getValue(), false) ?? "\u2014"}
        </UncertaintyMarker>
      );
    },
  }),
  columnHelper.accessor("dateEnd", {
    header: "To",
    cell: (info) => {
      const row = info.row.original;
      return (
        <UncertaintyMarker
          uncertain={row.dateEndUncertain}
          notes={row.notes.length > 0 ? row.notes : undefined}
        >
          {formatYearUncertain(info.getValue(), false) ?? "\u2014"}
        </UncertaintyMarker>
    ),
  }),
  columnHelper.accessor("sources", {
    header: "Sources",
    cell: (info) => (
      <div className="flex flex-wrap gap-1">
        {info.getValue().map((s) => (
          <SourceBadge key={s.id} name={s.name} />
        ))}
      </div>
    ),
    enableSorting: false,
  }),
];

interface StatusAssertionsTableProps {
  data: StatusAssertion[];
}

export function StatusAssertionsTable({ data }: StatusAssertionsTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
  });

  if (data.length === 0) return null;

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
