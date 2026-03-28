import { useState, useCallback, useRef, useEffect } from "react";
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

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = () => setOpen(false);
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [open]);

  const persons = results.filter((r) => r.type === "person");
  const offices = results.filter((r) => r.type === "office");
  let flatIndex = 0;

  return (
    <div className="relative" onClick={(e) => e.stopPropagation()}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Input
            placeholder="Search persons, offices..."
            value={query}
            onChange={(e) => handleSearch(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              if (results.length > 0 && query.length > 0) setOpen(true);
            }}
            className="w-64"
          />
        </PopoverTrigger>
        <PopoverContent
          className="w-80 p-0"
          align="start"
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <div className="max-h-80 overflow-y-auto">
            {persons.length > 0 && (
              <div>
                <p className="px-3 py-1.5 text-xs font-medium text-ink-muted">Persons</p>
                {persons.map((r) => {
                  const idx = flatIndex++;
                  return (
                    <button
                      key={r.id}
                      className={`w-full px-3 py-2 text-left text-sm hover:bg-parchment-dark ${
                        idx === selectedIndex ? "bg-parchment-dark" : ""
                      }`}
                      onClick={() => navigateToResult(r)}
                    >
                      <span className="font-medium">{r.name}</span>
                      {r.era && <span className="ml-2 text-xs text-ink-muted">{r.era}</span>}
                      {r.highestOffice && (
                        <span className="ml-2 text-xs text-ink-muted">
                          &mdash; {r.highestOffice}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
            {offices.length > 0 && (
              <div>
                <p className="px-3 py-1.5 text-xs font-medium text-ink-muted">Offices</p>
                {offices.map((r) => {
                  const idx = flatIndex++;
                  return (
                    <button
                      key={r.id}
                      className={`w-full px-3 py-2 text-left text-sm hover:bg-parchment-dark ${
                        idx === selectedIndex ? "bg-parchment-dark" : ""
                      }`}
                      onClick={() => navigateToResult(r)}
                    >
                      <span className="font-medium">{r.name}</span>
                      {r.abbreviation && (
                        <span className="ml-2 text-xs text-ink-muted">({r.abbreviation})</span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
