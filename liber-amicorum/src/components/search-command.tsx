import { useState, useCallback, useRef, useMemo } from "react";
import { useNavigate } from "@tanstack/react-router";
import { search, type SearchResult } from "#/lib/search";
import { Input } from "#/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "#/components/ui/popover";

export function SearchCommand() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const navigate = useNavigate();
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const handleSearch = useCallback((value: string) => {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const res = search(value);
      setResults(res.slice(0, 10));
      setSelectedIndex(0);
      setOpen(res.length > 0 && value.length > 0);
    }, 150);
  }, []);

  const navigateToResult = useCallback(
    (result: SearchResult) => {
      setOpen(false);
      setQuery("");
      if (result.type === "person") {
        navigate({ to: "/persons/$personId", params: { personId: result.id } });
      } else {
        navigate({ to: "/offices/$officeId", params: { officeId: result.id } });
      }
    },
    [navigate],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter" && results[selectedIndex]) {
        e.preventDefault();
        navigateToResult(results[selectedIndex]);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    },
    [results, selectedIndex, navigateToResult],
  );

  // Pre-compute flat list with indices for concurrent-safe rendering
  const flatResults = useMemo(() => {
    const persons = results.filter((r) => r.type === "person");
    const offices = results.filter((r) => r.type === "office");
    const items: Array<{
      result: SearchResult;
      index: number;
      isGroupStart: boolean;
      group: string;
    }> = [];
    let idx = 0;
    for (const r of persons) {
      items.push({ result: r, index: idx++, isGroupStart: items.length === 0, group: "Persons" });
    }
    const officeStart = items.length;
    for (const r of offices) {
      items.push({
        result: r,
        index: idx++,
        isGroupStart: items.length === officeStart,
        group: "Offices",
      });
    }
    return items;
  }, [results]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={<Input />}
        placeholder="Search persons, offices..."
        value={query}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleSearch(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => {
          if (results.length > 0 && query.length > 0) setOpen(true);
        }}
        className="w-64"
      />
      <PopoverContent
        className="w-80 p-0"
        align="start"
        onOpenAutoFocus={(e) => e.preventDefault()}
        onInteractOutside={() => setOpen(false)}
      >
        <div className="max-h-80 overflow-y-auto">
          {flatResults.map((item) => (
            <div key={`${item.group}-${item.result.id}`}>
              {item.isGroupStart && (
                <p className="px-3 py-1.5 text-xs font-medium text-ink-muted">{item.group}</p>
              )}
              <button
                className={`w-full px-3 py-2 text-left text-sm hover:bg-parchment-dark ${
                  item.index === selectedIndex ? "bg-parchment-dark" : ""
                }`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  navigateToResult(item.result);
                }}
              >
                <span className="font-medium">{item.result.name}</span>
                {item.result.type === "person" && item.result.era && (
                  <span className="ml-2 text-xs text-ink-muted">{item.result.era}</span>
                )}
                {item.result.type === "person" && item.result.highestOffice && (
                  <span className="ml-2 text-xs text-ink-muted">
                    &mdash; {item.result.highestOffice}
                  </span>
                )}
                {item.result.type === "office" && item.result.abbreviation && (
                  <span className="ml-2 text-xs text-ink-muted">({item.result.abbreviation})</span>
                )}
              </button>
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
