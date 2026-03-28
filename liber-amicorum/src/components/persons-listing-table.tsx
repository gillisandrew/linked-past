import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import type { PersonIndex } from "#/lib/types";
import { formatEra } from "#/lib/format";
import { Input } from "#/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "#/components/ui/table";

const columnHelper = createColumnHelper<PersonIndex>();

const columns = [
  columnHelper.accessor("name", {
    header: "Name",
    cell: (info) => (
      <Link
        to="/persons/$personId"
        params={{ personId: info.row.original.id }}
        className="text-link hover:text-link-light underline decoration-link/30 hover:decoration-link"
      >
        {info.getValue()}
      </Link>
    ),
  }),
  columnHelper.accessor("nomen", {
    header: "Nomen",
    cell: (info) => info.getValue() ?? "",
  }),
  columnHelper.display({
    id: "era",
    header: "Era",
    cell: (info) => formatEra(info.row.original.eraFrom, info.row.original.eraTo),
    sortingFn: (a, b) => (a.original.eraFrom ?? 0) - (b.original.eraFrom ?? 0),
  }),
  columnHelper.accessor("highestOffice", {
    header: "Highest Office",
    cell: (info) => info.getValue() ?? "",
  }),
];

interface PersonsListingTableProps {
  data: PersonIndex[];
}

export function PersonsListingTable({ data }: PersonsListingTableProps) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "nomen", desc: false }]);
  const [globalFilter, setGlobalFilter] = useState("");

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    state: { sorting, globalFilter },
  });

  return (
    <div className="space-y-4">
      <Input
        placeholder="Filter persons..."
        value={globalFilter}
        onChange={(e) => setGlobalFilter(e.target.value)}
        className="max-w-sm"
      />

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

      <span className="text-sm text-ink-muted">
        {table.getFilteredRowModel().rows.length} results
      </span>
    </div>
  );
}
