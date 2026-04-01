import { Badge } from "@/components/ui/badge";
import { shortenPredicate } from "../lib/predicates";
import type { XrefLink } from "../lib/types";
import { EntityUri } from "./entity-uri";

const CONFIDENCE_COLORS: Record<string, string> = {
  confirmed: "bg-green-500 hover:bg-green-500",
  probable: "bg-yellow-500 hover:bg-yellow-500 text-black",
  candidate: "bg-gray-400 hover:bg-gray-400",
  concordance: "bg-blue-400 hover:bg-blue-400",
  "in-data": "bg-cyan-400 hover:bg-cyan-400",
};

export function XrefList({ links }: { links: XrefLink[] }) {
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
    <div className="space-y-3">
      {["confirmed", "probable", "candidate", "concordance", "in-data", "unknown"].map((conf) => {
        const items = groups.get(conf);
        if (!items) return null;
        const color = CONFIDENCE_COLORS[conf] ?? "bg-gray-400 hover:bg-gray-400";
        return (
          <div key={conf}>
            <Badge className={`text-[10px] mb-1 ${color}`}>{conf}</Badge>
            <div className="space-y-1 pl-2 border-l-2">
              {items.map((link, i) => (
                <div key={i} className="text-sm">
                  <span className="text-muted-foreground">{shortenPredicate(link.relationship)}</span>
                  {" → "}
                  <EntityUri uri={link.target} />
                  {link.basis && (
                    <span className="block text-xs text-muted-foreground">{link.basis}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
