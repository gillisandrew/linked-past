import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  useReactTable,
  type SortingState,
  type ColumnDef,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import { ExternalLink } from "lucide-react";
import type { OfficeHolder, OfficeHolderWithOffice } from "#/lib/types";
import { assertionAnchor, formatYearUncertain } from "#/lib/format";
import { AnchorRow } from "#/components/anchor-row";
import { PersonLink } from "#/components/person-link";
import { OfficeLink } from "#/components/office-link";
import { SourceBadge } from "#/components/source-badge";
import { LazyUncertaintyMarker } from "#/components/lazy-uncertainty-marker";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "#/components/ui/table";

const baseColumnHelper = createColumnHelper<OfficeHolderWithOffice>();

const personCol = baseColumnHelper.accessor("personName", {
  header: "Person",
  cell: (info) => <PersonLink id={info.row.original.personId} name={info.getValue()} />,
});

const officeCol = baseColumnHelper.accessor("officeName", {
  header: "Office",
  cell: (info) => <OfficeLink id={info.row.original.officeId} name={info.getValue()} />,
});

const dateStartCol = baseColumnHelper.accessor("dateStart", {
  header: "From",
  cell: (info) => {
    const row = info.row.original;
    return (
      <LazyUncertaintyMarker
        uncertain={row.dateStartUncertain}
        personId={row.personId}
        officeId={row.officeId}
        dateStart={row.dateStart}
      >
        {formatYearUncertain(info.getValue(), false) ?? "\u2014"}
      </LazyUncertaintyMarker>
    );
  },
});

const dateEndCol = baseColumnHelper.accessor("dateEnd", {
  header: "To",
  cell: (info) => {
    const row = info.row.original;
    return (
      <LazyUncertaintyMarker
        uncertain={row.dateEndUncertain}
        personId={row.personId}
        officeId={row.officeId}
        dateStart={row.dateStart}
      >
        {formatYearUncertain(info.getValue(), false) ?? "\u2014"}
      </LazyUncertaintyMarker>
    );
  },
});

const uncertainCol = baseColumnHelper.display({
  id: "assertion",
  header: "",
  cell: (info) => {
    const row = info.row.original;
    return (
      <LazyUncertaintyMarker
        uncertain={row.uncertain}
        personId={row.personId}
        officeId={row.officeId}
        dateStart={row.dateStart}
      >
        {row.uncertain ? "uncertain" : ""}
      </LazyUncertaintyMarker>
    );
  },
});

const sourcesCol = baseColumnHelper.accessor("sources", {
  header: "Sources",
  cell: (info) => (
    <div className="flex flex-wrap gap-1">
      {info.getValue().map((s) => (
        <SourceBadge key={s.id} name={s.name} id={s.id} />
      ))}
    </div>
  ),
  enableSorting: false,
});

interface HoldersTableProps {
  data: OfficeHolder[];
  /** If provided, shows an Office column and a sub-office filter */
  subOffices?: { id: string; name: string }[];
}

export function HoldersTable({ data, subOffices }: HoldersTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const hasSubOffices = subOffices && subOffices.length > 0;

  // All sub-office IDs selected by default
  const [selectedOffices, setSelectedOffices] = useState<Set<string>>(() => {
    if (!hasSubOffices) return new Set();
    // Include the parent office (rows where officeId matches the parent) plus all children
    const all = new Set(subOffices.map((s) => s.id));
    // Also include the parent — tagged holders will have the parent officeId
    for (const row of data as OfficeHolderWithOffice[]) {
      all.add(row.officeId);
    }
    return all;
  });

  const filteredData = useMemo(() => {
    if (!hasSubOffices) return data as OfficeHolderWithOffice[];
    return (data as OfficeHolderWithOffice[]).filter((h) => selectedOffices.has(h.officeId));
  }, [data, hasSubOffices, selectedOffices]);

  const columns = useMemo(() => {
    const cols: ColumnDef<OfficeHolderWithOffice, unknown>[] = [
      personCol as ColumnDef<OfficeHolderWithOffice, unknown>,
    ];
    if (hasSubOffices) {
      cols.push(officeCol as ColumnDef<OfficeHolderWithOffice, unknown>);
    }
    cols.push(
      dateStartCol as ColumnDef<OfficeHolderWithOffice, unknown>,
      dateEndCol as ColumnDef<OfficeHolderWithOffice, unknown>,
      uncertainCol as ColumnDef<OfficeHolderWithOffice, unknown>,
      sourcesCol as ColumnDef<OfficeHolderWithOffice, unknown>,
    );
    return cols;
  }, [hasSubOffices]);

  const table = useReactTable({
    data: filteredData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
  });

  if (data.length === 0) return null;

  // Collect unique office names for the filter
  const officeOptions = useMemo(() => {
    if (!hasSubOffices) return [];
    const seen = new Map<string, string>();
    for (const h of data as OfficeHolderWithOffice[]) {
      if (!seen.has(h.officeId)) {
        seen.set(h.officeId, h.officeName);
      }
    }
    return Array.from(seen.entries()).map(([id, name]) => ({ id, name }));
  }, [data, hasSubOffices]);

  const toggleOffice = (officeId: string) => {
    setSelectedOffices((prev) => {
      const next = new Set(prev);
      if (next.has(officeId)) {
        next.delete(officeId);
      } else {
        next.add(officeId);
      }
      return next;
    });
  };

  return (
    <div className="space-y-3">
      {/* Sub-office filter */}
      {hasSubOffices && officeOptions.length > 1 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-ink-muted">Filter by office:</span>
          {officeOptions.map((opt) => {
            const active = selectedOffices.has(opt.id);
            return (
              <span
                key={opt.id}
                className={`inline-flex items-stretch rounded-full border text-xs transition-colors ${
                  active
                    ? "border-link bg-link/10 text-link"
                    : "border-ink/15 text-ink-muted hover:border-ink/30"
                }`}
              >
                <button
                  onClick={() => toggleOffice(opt.id)}
                  className="px-3 py-1 hover:opacity-80"
                >
                  {opt.name}
                </button>
                <Link
                  to="/offices/$officeId"
                  params={{ officeId: opt.id }}
                  className={`flex items-center border-l px-1.5 py-1 hover:opacity-80 ${
                    active ? "border-link/30" : "border-ink/10"
                  }`}
                  title={`Go to ${opt.name}`}
                >
                  <ExternalLink className="h-3 w-3" />
                </Link>
              </span>
            );
          })}
        </div>
      )}

      <div className="text-xs text-ink-muted">
        {filteredData.length} holder{filteredData.length !== 1 ? "s" : ""}
        {hasSubOffices && filteredData.length !== data.length && ` (of ${data.length} total)`}
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
            <AnchorRow
              id={assertionAnchor("holder", row.original.personId, row.original.dateStart)}
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
    </div>
  );
}
