import {
  Bookmark,
  Database,
  FileText,
  Link2,
  Search,
  User,
  X,
} from "lucide-react";
import type { ViewerMessage } from "../lib/types";

const TYPE_OPTIONS = ["query", "entity", "links", "search", "report"] as const;

const TYPE_META: Record<string, { icon: React.ReactNode; color: string }> = {
  query: { icon: <Database className="w-2.5 h-2.5" />, color: "text-blue-600 dark:text-blue-400" },
  search: { icon: <Search className="w-2.5 h-2.5" />, color: "text-violet-600 dark:text-violet-400" },
  entity: { icon: <User className="w-2.5 h-2.5" />, color: "text-emerald-600 dark:text-emerald-400" },
  links: { icon: <Link2 className="w-2.5 h-2.5" />, color: "text-amber-600 dark:text-amber-400" },
  report: { icon: <FileText className="w-2.5 h-2.5" />, color: "text-rose-600 dark:text-rose-400" },
};

export type Filters = {
  types: Set<string>;
  datasets: Set<string>;
  bookmarkedOnly: boolean;
  hideEmpty: boolean;
};

export function emptyFilters(): Filters {
  return { types: new Set(), datasets: new Set(), bookmarkedOnly: false, hideEmpty: false };
}

function isEmptyResult(msg: ViewerMessage): boolean {
  if (msg.type === "query") return msg.data.row_count === 0;
  if (msg.type === "search") return msg.data.results.length === 0;
  if (msg.type === "links") return msg.data.links.length === 0;
  return false;
}

export function applyFilters(
  messages: ViewerMessage[],
  filters: Filters,
  bookmarks: Set<number>,
): ViewerMessage[] {
  return messages.filter((msg) => {
    if (filters.bookmarkedOnly && !bookmarks.has(msg.seq)) return false;
    if (filters.hideEmpty && isEmptyResult(msg)) return false;
    if (filters.types.size > 0 && !filters.types.has(msg.type)) return false;
    if (filters.datasets.size > 0 && msg.dataset && !filters.datasets.has(msg.dataset)) return false;
    return true;
  });
}

function ToggleChip({
  label,
  icon,
  active,
  onClick,
}: {
  label: string;
  icon?: React.ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] font-medium cursor-pointer transition-colors select-none ${
        active
          ? "text-foreground"
          : "text-muted-foreground/60 hover:text-muted-foreground"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

export function FeedFilters({
  messages,
  filters,
  bookmarkCount,
  onChange,
}: {
  messages: ViewerMessage[];
  filters: Filters;
  bookmarkCount: number;
  onChange: (f: Filters) => void;
}) {
  const datasets = [...new Set(messages.map((m) => m.dataset).filter(Boolean) as string[])].sort();
  const activeTypes = [...new Set(messages.map((m) => m.type))];

  function toggleType(t: string) {
    const next = new Set(filters.types);
    if (next.has(t)) next.delete(t);
    else next.add(t);
    onChange({ ...filters, types: next });
  }

  function toggleDataset(ds: string) {
    const next = new Set(filters.datasets);
    if (next.has(ds)) next.delete(ds);
    else next.add(ds);
    onChange({ ...filters, datasets: next });
  }

  function toggleBookmarked() {
    onChange({ ...filters, bookmarkedOnly: !filters.bookmarkedOnly });
  }

  function clearAll() {
    onChange(emptyFilters());
  }

  const emptyCount = messages.filter(isEmptyResult).length;

  function toggleHideEmpty() {
    onChange({ ...filters, hideEmpty: !filters.hideEmpty });
  }

  const hasFilters = filters.types.size > 0 || filters.datasets.size > 0 || filters.bookmarkedOnly || filters.hideEmpty;

  return (
    <div className="flex items-center gap-2 flex-wrap text-xs">
      <span className="text-muted-foreground font-medium">Filter:</span>
      {bookmarkCount > 0 && (
        <>
          <ToggleChip
            label={`${bookmarkCount}`}
            icon={<Bookmark className="w-3 h-3" />}
            active={filters.bookmarkedOnly}
            onClick={toggleBookmarked}
          />
          <span className="text-border">·</span>
        </>
      )}
      {emptyCount > 0 && (
        <>
          <ToggleChip
            label={`hide empty (${emptyCount})`}
            active={filters.hideEmpty}
            onClick={toggleHideEmpty}
          />
          <span className="text-border">·</span>
        </>
      )}
      {TYPE_OPTIONS.filter((t) => activeTypes.includes(t)).map((t) => {
        const meta = TYPE_META[t];
        return (
          <ToggleChip
            key={t}
            label={t}
            icon={<span className={meta.color}>{meta.icon}</span>}
            active={filters.types.has(t)}
            onClick={() => toggleType(t)}
          />
        );
      })}
      {datasets.length > 0 && (
        <>
          <span className="text-border">·</span>
          {datasets.map((ds) => (
            <ToggleChip key={ds} label={ds} active={filters.datasets.has(ds)} onClick={() => toggleDataset(ds)} />
          ))}
        </>
      )}
      {hasFilters && (
        <button
          onClick={clearAll}
          className="inline-flex items-center gap-0.5 text-[11px] text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
          title="Clear all filters"
        >
          <X className="w-3 h-3" />
          <span>clear</span>
        </button>
      )}
    </div>
  );
}
