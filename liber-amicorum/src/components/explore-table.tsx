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
  type SortingState,
  type VisibilityState,
} from "@tanstack/react-table";
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { SlidersHorizontal } from "lucide-react";
import type { PersonIndex } from "#/lib/types";
import { formatEra } from "#/lib/format";
import { UncertaintyMarker } from "#/components/uncertainty-marker";
import { Input } from "#/components/ui/input";
import { Button } from "#/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "#/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "#/components/ui/select";
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
        <Input
          placeholder="Filter all columns..."
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          className="max-w-sm"
        />
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
      </div>

      {/* Facet filters */}
      <div className="flex flex-wrap items-center gap-2">
        <FacetSelect column={table.getColumn("sex")} label="Sex" />
        <FacetBooleanSelect column={table.getColumn("patrician")} label="Patrician" />
        <FacetBooleanSelect column={table.getColumn("nobilis")} label="Nobilis" />
        <FacetBooleanSelect column={table.getColumn("novus")} label="Novus" />
        <EraRangeFilter table={table} />
      </div>

      {/* Table */}
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

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-ink-muted">
          {table.getFilteredRowModel().rows.length} results
        </span>
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

function FacetSelect({
  column,
  label,
}: {
  column: Column<PersonIndex, unknown> | undefined;
  label: string;
}) {
  if (!column) return null;
  const facetValues = column.getFacetedUniqueValues();
  const currentValue = (column.getFilterValue() as string) ?? "";

  return (
    <Select
      value={currentValue}
      onValueChange={(val) => column.setFilterValue(val === "__all__" ? undefined : val)}
    >
      <SelectTrigger className="h-8 w-auto min-w-[120px] text-xs">
        <SelectValue placeholder={label} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__all__">All {label}</SelectItem>
        {[...facetValues.entries()]
          .sort((a, b) => b[1] - a[1])
          .map(([val, count]) => (
            <SelectItem key={String(val)} value={String(val)}>
              {String(val)} ({count.toLocaleString()})
            </SelectItem>
          ))}
      </SelectContent>
    </Select>
  );
}

function FacetBooleanSelect({
  column,
  label,
}: {
  column: Column<PersonIndex, unknown> | undefined;
  label: string;
}) {
  if (!column) return null;
  const facetValues = column.getFacetedUniqueValues();
  const currentValue = column.getFilterValue();
  const yesCount = facetValues.get(true) ?? 0;
  const noCount = facetValues.get(false) ?? facetValues.get(undefined) ?? 0;

  const selectValue = currentValue === true ? "yes" : currentValue === false ? "no" : "__all__";

  return (
    <Select
      value={selectValue}
      onValueChange={(val) => {
        if (val === "__all__") column.setFilterValue(undefined);
        else if (val === "yes") column.setFilterValue(true);
        else column.setFilterValue(false);
      }}
    >
      <SelectTrigger className="h-8 w-auto min-w-[120px] text-xs">
        <SelectValue placeholder={label} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__all__">All {label}</SelectItem>
        <SelectItem value="yes">Yes ({yesCount.toLocaleString()})</SelectItem>
        <SelectItem value="no">No ({noCount.toLocaleString()})</SelectItem>
      </SelectContent>
    </Select>
  );
}

function EraRangeFilter({ table }: { table: ReturnType<typeof useReactTable<PersonIndex>> }) {
  const column = table.getColumn("era");
  if (!column) return null;
  const [min, max] = column.getFacetedMinMaxValues() ?? [0, 0];
  const currentValue = (column.getFilterValue() as [number | undefined, number | undefined]) ?? [
    undefined,
    undefined,
  ];

  return (
    <div className="flex items-center gap-1 text-xs">
      <span className="text-ink-muted">Era:</span>
      <Input
        type="number"
        placeholder={`${min}`}
        value={currentValue[0] ?? ""}
        onChange={(e) => {
          const val = e.target.value ? Number(e.target.value) : undefined;
          column.setFilterValue([val, currentValue[1]]);
        }}
        className="h-8 w-20 text-xs"
      />
      <span className="text-ink-muted">to</span>
      <Input
        type="number"
        placeholder={`${max}`}
        value={currentValue[1] ?? ""}
        onChange={(e) => {
          const val = e.target.value ? Number(e.target.value) : undefined;
          column.setFilterValue([currentValue[0], val]);
        }}
        className="h-8 w-20 text-xs"
      />
    </div>
  );
}
