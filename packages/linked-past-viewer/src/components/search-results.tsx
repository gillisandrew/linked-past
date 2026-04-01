import type { SearchData } from "../lib/types";
import { DatasetBadge } from "./dataset-badge";
import { EntityUri } from "./entity-uri";

export function SearchResults({ data }: { data: SearchData }) {
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
    <div className="space-y-3">
      <p className="text-sm">
        Results for &ldquo;{data.query_text}&rdquo;
      </p>
      {[...groups.entries()].map(([ds, results]) => (
        <div key={ds}>
          <DatasetBadge dataset={ds} />
          <div className="mt-1 space-y-1">
            {results.map((r, i) => (
              <div key={i} className="text-sm">
                <span className="font-medium">{r.label}</span>
                <EntityUri uri={r.uri} />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
