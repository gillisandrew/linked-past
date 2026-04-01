import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { humanizePredicate } from "../lib/predicates";
import type { EntityData } from "../lib/types";
import { DatasetBadge } from "./dataset-badge";
import { PropertyValue } from "./property-value";

/**
 * Predicates to hide from popovers — structural/meta, not human-readable.
 */
const HIDDEN_PREDICATES = new Set([
  "type", "rdf:type", "Class", "subClassOf", "subPropertyOf",
  "domain", "range", "equivalentClass", "equivalentProperty",
  "sameAs", "differentFrom", "disjointWith", "imports",
  "versionInfo", "isDefinedBy", "first", "rest",
  // DPRR internal IDs
  "hasID", "hasDprrID",
]);

/**
 * Predicates to hide object values for (just show predicate exists).
 */
const HIDE_VALUES = new Set([
  "hasAssociatedWebpage",
]);

function localName(pred: string): string {
  return pred.split("/").pop()?.split("#").pop() ?? pred;
}

export function EntityPopoverContent({ data }: { data: EntityData }) {
  const humanProps = data.properties.filter(
    (p) => !HIDDEN_PREDICATES.has(localName(p.pred)),
  );
  // Deduplicate by predicate (show first value only)
  const seen = new Set<string>();
  const deduped = humanProps.filter((p) => {
    const local = localName(p.pred);
    if (seen.has(local)) return false;
    seen.add(local);
    return true;
  });
  const topProps = deduped.slice(0, 6);

  return (
    <Card className="border-0 shadow-none w-[420px]">
      <CardHeader className="p-3 pb-1">
        <div className="flex items-center gap-1.5">
          {data.dataset && <DatasetBadge dataset={data.dataset} />}
          <span className="text-xs text-muted-foreground font-mono truncate">
            {data.uri.split("/").pop()}
          </span>
        </div>
        <CardTitle className="text-base">{data.name}</CardTitle>
      </CardHeader>
      <CardContent className="p-3 pt-0">
        {topProps.length > 0 && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            {topProps.map((p, i) => {
              const local = localName(p.pred);
              return (
                <div key={i} className="contents">
                  <dt className="font-semibold text-muted-foreground">{humanizePredicate(p.pred)}</dt>
                  <dd className="truncate">
                    {HIDE_VALUES.has(local) ? (
                      <span className="text-muted-foreground italic">link</span>
                    ) : (
                      <PropertyValue value={p.obj} />
                    )}
                  </dd>
                </div>
              );
            })}
          </dl>
        )}
        {data.xrefs.length > 0 && (
          <div className="mt-2 pt-2 border-t text-xs text-muted-foreground">
            {data.xrefs.length} cross-reference{data.xrefs.length !== 1 ? "s" : ""}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
