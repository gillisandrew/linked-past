import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getExpandedRowModel,
  getSortedRowModel,
  useReactTable,
  type ExpandedState,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { OfficeTreeNode } from "#/lib/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "#/components/ui/table";

const columnHelper = createColumnHelper<OfficeTreeNode>();

const columns = [
  columnHelper.accessor("name", {
    header: "Name",
    cell: ({ row, getValue }) => (
      <div style={{ paddingLeft: `${row.depth * 1.5}rem` }} className="flex items-center gap-1">
        {row.getCanExpand() ? (
          <button
            onClick={row.getToggleExpandedHandler()}
            className="p-0.5 text-ink-muted hover:text-ink"
          >
            {row.getIsExpanded() ? (
              <ChevronDown className="h-3.5 w-3.5 text-ink-muted" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5 text-ink-muted" />
            )}
          </button>
        ) : (
          <span className="w-4" />
        )}
        <Link
          to="/offices/$officeId"
          params={{ officeId: row.original.id }}
          className="text-link hover:text-link-light underline decoration-link/30 hover:decoration-link truncate max-w-md inline-block align-bottom"
          title={getValue()}
        >
          {getValue()}
        </Link>
      </div>
    ),
  }),
  columnHelper.accessor("abbreviation", {
    header: "Abbreviation",
    cell: (info) => info.getValue() ?? "",
  }),
  columnHelper.accessor("holderCount", {
    header: "Holders",
  }),
];

interface OfficesListingTableProps {
  data: OfficeTreeNode[];
}

export function OfficesListingTable({ data }: OfficesListingTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [expanded, setExpanded] = useState<ExpandedState>(true);

  const table = useReactTable({
    data,
    columns,
    getSubRows: (row) => (row.subOffices.length > 0 ? row.subOffices : undefined),
    getCoreRowModel: getCoreRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    onExpandedChange: setExpanded,
    state: { sorting, expanded },
  });

  return (
    <Table className="table-fixed">
      <colgroup>
        <col className="w-[55%]" />
        <col className="w-[25%]" />
        <col className="w-[20%]" />
      </colgroup>
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
          <TableRow key={row.id} id={`office-${row.original.id}`}>
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
