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

const TYPE_ICONS: Record<string, React.ReactNode> = {
  query: <Database className="w-3 h-3" />,
  search: <Search className="w-3 h-3" />,
  entity: <User className="w-3 h-3" />,
  links: <Link2 className="w-3 h-3" />,
  report: <FileText className="w-3 h-3" />,
};

export type Filters = {
  types: Set<string>;
  datasets: Set<string>;
  bookmarkedOnly: boolean;
};

export function emptyFilters(): Filters {
  return { types: new Set(), datasets: new Set(), bookmarkedOnly: false };
}

export function applyFilters(
  messages: ViewerMessage[],
  filters: Filters,
  bookmarks: Set<number>,
): ViewerMessage[] {
  return messages.filter((msg) => {
    if (filters.bookmarkedOnly && !bookmarks.has(msg.seq)) return false;
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
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border transition-colors cursor-pointer ${
        active
          ? "bg-primary text-primary-foreground border-primary"
          : "bg-transparent text-muted-foreground border-border hover:border-foreground/30"
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

  const hasFilters = filters.types.size > 0 || filters.datasets.size > 0 || filters.bookmarkedOnly;

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
          <span className="text-muted-foreground/40">|</span>
        </>
      )}
      {TYPE_OPTIONS.filter((t) => activeTypes.includes(t)).map((t) => (
        <ToggleChip key={t} label={t} icon={TYPE_ICONS[t]} active={filters.types.has(t)} onClick={() => toggleType(t)} />
      ))}
      {datasets.length > 0 && (
        <>
          <span className="text-muted-foreground/40">|</span>
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
