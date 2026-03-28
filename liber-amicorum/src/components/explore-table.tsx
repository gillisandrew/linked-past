import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFacetedMinMaxValues,
  getFacetedRowModel,
  getFacetedUniqueValues,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type Column,
  type ColumnFiltersState,
  type Header,
  type SortingState,
  type VisibilityState,
} from "@tanstack/react-table";
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { SlidersHorizontal } from "lucide-react";
import type { PersonIndex } from "#/lib/types";
import { formatEra } from "#/lib/format";
import { UncertaintyMarker } from "#/components/uncertainty-marker";
import { Button } from "#/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "#/components/ui/dropdown-menu";
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
  }),
  columnHelper.accessor("cognomen", {
    header: "Cognomen",
  }),
  columnHelper.accessor("praenomen", {
    header: "Praenomen",
  }),
  columnHelper.accessor("eraFrom", {
    id: "era",
    header: "Era",
    cell: (info) => formatEra(info.row.original.eraFrom, info.row.original.eraTo),
    sortingFn: (a, b) => (a.original.eraFrom ?? 0) - (b.original.eraFrom ?? 0),
    filterFn: (row, _columnId, filterValue: [number | undefined, number | undefined]) => {
      const [min, max] = filterValue;
      const from = row.original.eraFrom;
      if (from == null) return false;
      if (min != null && from < min) return false;
      if (max != null && from > max) return false;
      return true;
    },
  }),
  columnHelper.accessor("sex", {
    header: "Sex",
  }),
  columnHelper.accessor("highestOffice", {
    header: "Highest Office",
  }),
  columnHelper.accessor("patrician", {
    header: "Patrician",
    cell: (info) => {
      const val = info.getValue();
      if (!val) return "";
      return (
        <UncertaintyMarker uncertain={info.row.original.patricianUncertain}>Yes</UncertaintyMarker>
      );
    },
  }),
  columnHelper.accessor("nobilis", {
    header: "Nobilis",
    cell: (info) => (info.getValue() ? "Yes" : ""),
  }),
  columnHelper.accessor("novus", {
    header: "Novus",
    cell: (info) => (info.getValue() ? "Yes" : ""),
  }),
  columnHelper.accessor("origin", {
    header: "Origin",
  }),
];

interface ExploreTableProps {
  data: PersonIndex[];
}

export function ExploreTable({ data }: ExploreTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({
    praenomen: false,
    origin: false,
  });
  const [globalFilter, setGlobalFilter] = useState("");

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getFacetedRowModel: getFacetedRowModel(),
    getFacetedUniqueValues: getFacetedUniqueValues(),
    getFacetedMinMaxValues: getFacetedMinMaxValues(),
    getPaginationRowModel: getPaginationRowModel(),
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onGlobalFilterChange: setGlobalFilter,
    state: { sorting, columnFilters, columnVisibility, globalFilter },
    initialState: { pagination: { pageSize: 50 } },
  });

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-4">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              <SlidersHorizontal className="h-4 w-4 mr-1" /> Columns
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {table
              .getAllColumns()
              .filter((col) => col.getCanHide())
              .map((col) => (
                <DropdownMenuCheckboxItem
                  key={col.id}
                  checked={col.getIsVisible()}
                  onCheckedChange={(value) => col.toggleVisibility(!!value)}
                >
                  {typeof col.columnDef.header === "string" ? col.columnDef.header : col.id}
                </DropdownMenuCheckboxItem>
              ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <span className="text-sm text-ink-muted">
          {table.getFilteredRowModel().rows.length} results
        </span>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHead key={header.id} className="align-top">
                  <div
                    className={
                      header.column.getCanSort() ? "cursor-pointer select-none" : undefined
                    }
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                    {{ asc: " \u2191", desc: " \u2193" }[header.column.getIsSorted() as string] ??
                      ""}
                  </div>
                  <ColumnFilter header={header} />
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

      {/* Pagination */}
      <div className="flex items-center justify-end">
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            Previous
          </Button>
          <span className="text-sm text-ink-muted">
            Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}

const TEXT_COLUMNS = new Set(["name", "nomen", "cognomen", "praenomen", "highestOffice", "origin"]);
const BOOLEAN_COLUMNS = new Set(["patrician", "nobilis", "novus"]);
const SELECT_COLUMNS = new Set(["sex"]);

function ColumnFilter({ header }: { header: Header<PersonIndex, unknown> }) {
  const column = header.column;
  const id = column.id;

  if (id === "era") {
    return <EraRangeFilterInline column={column} />;
  }
  if (TEXT_COLUMNS.has(id)) {
    return <TextFilterInline column={column} />;
  }
  if (SELECT_COLUMNS.has(id)) {
    return <SelectFilterInline column={column} />;
  }
  if (BOOLEAN_COLUMNS.has(id)) {
    return <BooleanFilterInline column={column} />;
  }
  return null;
}

function TextFilterInline({ column }: { column: Column<PersonIndex, unknown> }) {
  const value = (column.getFilterValue() as string) ?? "";
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => column.setFilterValue(e.target.value || undefined)}
      placeholder="Filter..."
      onClick={(e) => e.stopPropagation()}
      className="mt-1 block w-full rounded border border-ink/15 bg-white/60 px-1.5 py-0.5 text-xs text-ink placeholder:text-ink/30 focus:outline-none focus:ring-1 focus:ring-link/30"
    />
  );
}

function SelectFilterInline({ column }: { column: Column<PersonIndex, unknown> }) {
  const facetValues = column.getFacetedUniqueValues();
  const currentValue = (column.getFilterValue() as string) ?? "";

  return (
    <select
      value={currentValue}
      onChange={(e) => column.setFilterValue(e.target.value || undefined)}
      onClick={(e) => e.stopPropagation()}
      className="mt-1 block w-full rounded border border-ink/15 bg-white/60 px-1 py-0.5 text-xs text-ink focus:outline-none focus:ring-1 focus:ring-link/30"
    >
      <option value="">All</option>
      {[...facetValues.entries()]
        .sort((a, b) => b[1] - a[1])
        .map(([val, count]) => (
          <option key={String(val)} value={String(val)}>
            {String(val)} ({count.toLocaleString()})
          </option>
        ))}
    </select>
  );
}

function BooleanFilterInline({ column }: { column: Column<PersonIndex, unknown> }) {
  const facetValues = column.getFacetedUniqueValues();
  const currentValue = column.getFilterValue();
  const yesCount = facetValues.get(true) ?? 0;
  const noCount = facetValues.get(false) ?? facetValues.get(undefined) ?? 0;

  const selectValue = currentValue === true ? "yes" : currentValue === false ? "no" : "";

  return (
    <select
      value={selectValue}
      onChange={(e) => {
        const val = e.target.value;
        if (val === "") column.setFilterValue(undefined);
        else if (val === "yes") column.setFilterValue(true);
        else column.setFilterValue(false);
      }}
      onClick={(e) => e.stopPropagation()}
      className="mt-1 block w-full rounded border border-ink/15 bg-white/60 px-1 py-0.5 text-xs text-ink focus:outline-none focus:ring-1 focus:ring-link/30"
    >
      <option value="">All</option>
      <option value="yes">Yes ({yesCount.toLocaleString()})</option>
      <option value="no">No ({noCount.toLocaleString()})</option>
    </select>
  );
}

function EraRangeFilterInline({ column }: { column: Column<PersonIndex, unknown> }) {
  const [min, max] = column.getFacetedMinMaxValues() ?? [0, 0];
  const currentValue = (column.getFilterValue() as [number | undefined, number | undefined]) ?? [
    undefined,
    undefined,
  ];

  return (
    <div className="mt-1 flex items-center gap-1">
      <input
        type="number"
        placeholder={`${min}`}
        value={currentValue[0] ?? ""}
        onChange={(e) => {
          const val = e.target.value ? Number(e.target.value) : undefined;
          column.setFilterValue([val, currentValue[1]]);
        }}
        onClick={(e) => e.stopPropagation()}
        className="block w-14 rounded border border-ink/15 bg-white/60 px-1 py-0.5 text-xs text-ink placeholder:text-ink/30 focus:outline-none focus:ring-1 focus:ring-link/30"
      />
      <span className="text-[10px] text-ink-muted">-</span>
      <input
        type="number"
        placeholder={`${max}`}
        value={currentValue[1] ?? ""}
        onChange={(e) => {
          const val = e.target.value ? Number(e.target.value) : undefined;
          column.setFilterValue([currentValue[0], val]);
        }}
        onClick={(e) => e.stopPropagation()}
        className="block w-14 rounded border border-ink/15 bg-white/60 px-1 py-0.5 text-xs text-ink placeholder:text-ink/30 focus:outline-none focus:ring-1 focus:ring-link/30"
      />
    </div>
  );
}
