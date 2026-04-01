import { useState } from "react";
import type { SearchData } from "../lib/types";
import { DATASETS } from "../lib/datasets";
import { DatasetBadge } from "./dataset-badge";
import { EntityUri } from "./entity-uri";

const MAX_PER_GROUP = 5;

export function SearchResults({ data }: { data: SearchData }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  if (data.results.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No entities found matching &ldquo;{data.query_text}&rdquo;.
      </p>
    );
  }

  // Group by dataset
  const groups = new Map<string, typeof data.results>();
  for (const r of data.results) {
    if (!groups.has(r.dataset)) groups.set(r.dataset, []);
    groups.get(r.dataset)!.push(r);
  }

  return (
    <div className="space-y-4">
      {[...groups.entries()].map(([ds, results]) => {
        const isExpanded = expanded.has(ds);
        const visible = isExpanded ? results : results.slice(0, MAX_PER_GROUP);
        const hiddenCount = results.length - MAX_PER_GROUP;
        const dsInfo = DATASETS[ds];
        const dsLabel = dsInfo?.name ?? ds;

        return (
          <div key={ds}>
            <div className="flex items-center gap-2 mb-2">
              <DatasetBadge dataset={ds} />
              <span className="text-xs text-muted-foreground">
                {dsLabel} — {results.length} result{results.length !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="space-y-0.5 ml-1 border-l-2 border-muted pl-3">
              {visible.map((r, i) => (
                <div
                  key={i}
                  className="py-1 flex items-baseline gap-2 text-sm hover:bg-muted/30 rounded px-1 -mx-1"
                >
                  <span className="font-medium flex-shrink-0">{r.label}</span>
                  <EntityUri uri={r.uri} showBadge={false} />
                </div>
              ))}
              {!isExpanded && hiddenCount > 0 && (
                <button
                  onClick={() => setExpanded((prev) => new Set([...prev, ds]))}
                  className="text-xs text-primary cursor-pointer hover:underline py-1 px-1"
                >
                  +{hiddenCount} more
                </button>
              )}
              {isExpanded && hiddenCount > 0 && (
                <button
                  onClick={() => setExpanded((prev) => { const next = new Set(prev); next.delete(ds); return next; })}
                  className="text-xs text-muted-foreground cursor-pointer hover:underline py-1 px-1"
                >
                  show less
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
