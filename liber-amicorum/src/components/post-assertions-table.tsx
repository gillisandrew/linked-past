import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import type { PostAssertion } from "#/lib/types";
import { assertionAnchor, formatYearUncertain } from "#/lib/format";
import { AnchorRow } from "#/components/anchor-row";
import { OfficeLink } from "#/components/office-link";
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

const columnHelper = createColumnHelper<PostAssertion>();

const columns = [
  columnHelper.accessor("office", {
    header: "Office",
    cell: (info) => <OfficeLink id={info.row.original.officeId} name={info.getValue()} />,
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
      );
    },
  }),
  columnHelper.accessor("province", {
    header: "Province",
    cell: (info) => {
      const val = info.getValue();
      if (!val) return "\u2014";
      const row = info.row.original;
      return (
        <UncertaintyMarker
          uncertain={row.provinceUncertain}
          notes={row.notes.length > 0 ? row.notes : undefined}
        >
          {val}
        </UncertaintyMarker>
      );
    },
  }),
  columnHelper.display({
    id: "assertion",
    header: "",
    cell: (info) => {
      const row = info.row.original;
      return (
        <UncertaintyMarker
          uncertain={row.uncertain}
          notes={row.notes.length > 0 ? row.notes : undefined}
        >
          {row.uncertain ? "uncertain" : ""}
        </UncertaintyMarker>
      );
    },
  }),
  columnHelper.accessor("sources", {
    header: "Sources",
    cell: (info) => (
      <div className="flex flex-wrap gap-1">
        {info.getValue().map((s) => (
          <SourceBadge key={s.id} name={s.name} id={s.id} />
        ))}
      </div>
    ),
    enableSorting: false,
  }),
];

interface PostAssertionsTableProps {
  data: PostAssertion[];
}

export function PostAssertionsTable({ data }: PostAssertionsTableProps) {
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
          <AnchorRow
            id={assertionAnchor("pa", row.original.officeId, row.original.dateStart)}
            key={row.id}
          >
            {row.getVisibleCells().map((cell) => (
              <TableCell key={cell.id}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </TableCell>
            ))}
          </AnchorRow>
        ))}
      </TableBody>
    </Table>
  );
}
