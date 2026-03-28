import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import type { OfficeHolder } from "#/lib/types";
import { formatYearUncertain } from "#/lib/format";
import { PersonLink } from "#/components/person-link";
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

const columnHelper = createColumnHelper<OfficeHolder>();

const columns = [
  columnHelper.accessor("personName", {
    header: "Person",
    cell: (info) => <PersonLink id={info.row.original.personId} name={info.getValue()} />,
  }),
  columnHelper.accessor("dateStart", {
    header: "From",
    cell: (info) => (
      <UncertaintyMarker uncertain={info.row.original.dateStartUncertain}>
        {formatYearUncertain(info.getValue(), false) ?? "\u2014"}
      </UncertaintyMarker>
    ),
  }),
  columnHelper.accessor("dateEnd", {
    header: "To",
    cell: (info) => (
      <UncertaintyMarker uncertain={info.row.original.dateEndUncertain}>
        {formatYearUncertain(info.getValue(), false) ?? "\u2014"}
      </UncertaintyMarker>
    ),
  }),
  columnHelper.display({
    id: "assertion",
    header: "",
    cell: (info) => (
      <UncertaintyMarker uncertain={info.row.original.uncertain}>
        {info.row.original.uncertain ? "uncertain" : ""}
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

interface HoldersTableProps {
  data: OfficeHolder[];
}

export function HoldersTable({ data }: HoldersTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
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
