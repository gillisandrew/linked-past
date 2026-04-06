import { useState } from "react";
import { shortenPredicate } from "../lib/predicates";
import type { XrefLink } from "../lib/types";
import { EntityUri } from "./entity-uri";

const MAX_VISIBLE = 3;

export function XrefList({ links }: { links: XrefLink[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  if (links.length === 0) {
    return <p className="text-sm text-muted-foreground">No cross-references found.</p>;
  }

  // Group by confidence
  const groups = new Map<string, XrefLink[]>();
  for (const link of links) {
    const conf = link.confidence || "unknown";
    if (!groups.has(conf)) groups.set(conf, []);
    groups.get(conf)!.push(link);
  }

  return (
    <div className="divide-y divide-border">
      {["confirmed", "probable", "candidate", "concordance", "in-data", "unknown"].map((conf) => {
        const items = groups.get(conf);
        if (!items) return null;
        const isExpanded = expanded.has(conf);
        const visible = isExpanded ? items : items.slice(0, MAX_VISIBLE);
        const hiddenCount = items.length - MAX_VISIBLE;

        return (
          <div key={conf} className="py-2 first:pt-0">
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">{conf} ({items.length})</span>
            <div className="space-y-1 mt-1">
              {visible.map((link, i) => (
                <div key={i} className="text-sm">
                  <span className="text-muted-foreground">{shortenPredicate(link.relationship)}</span>
                  {" → "}
                  <EntityUri uri={link.target} />
                  {link.basis && (
                    <span className="block text-xs text-muted-foreground">{link.basis}</span>
                  )}
                </div>
              ))}
              {!isExpanded && hiddenCount > 0 && (
                <button
                  onClick={() => setExpanded((prev) => new Set([...prev, conf]))}
                  className="text-xs text-primary cursor-pointer hover:underline"
                >
                  +{hiddenCount} more
                </button>
              )}
              {isExpanded && hiddenCount > 0 && (
                <button
                  onClick={() => setExpanded((prev) => { const next = new Set(prev); next.delete(conf); return next; })}
                  className="text-xs text-muted-foreground cursor-pointer hover:underline"
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
