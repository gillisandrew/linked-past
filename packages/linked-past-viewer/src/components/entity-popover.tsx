import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { humanizePredicate } from "../lib/predicates";
import type { EntityData } from "../lib/types";
import { DatasetBadge } from "./dataset-badge";
import { PropertyValue } from "./property-value";

const HIDDEN_PREDICATES = new Set([
  "type", "rdf:type", "Class", "subClassOf", "subPropertyOf",
  "domain", "range", "equivalentClass", "equivalentProperty",
  "sameAs", "differentFrom", "disjointWith", "imports",
  "versionInfo", "isDefinedBy", "first", "rest",
  "hasID", "hasDprrID", "hasAssociatedWebpage",
  "label", "prefLabel", "comment", "seeAlso",
]);

function localName(pred: string): string {
  return pred.split("/").pop()?.split("#").pop() ?? pred;
}

export function EntityPopoverContent({ data }: { data: EntityData }) {
  const humanProps = data.properties.filter(
    (p) => !HIDDEN_PREDICATES.has(localName(p.pred)),
  );
  // Deduplicate by display label + value (catches hasName + hasPersonName both mapping to "Name")
  const seen = new Set<string>();
  const deduped = humanProps.filter((p) => {
    const key = `${humanizePredicate(p.pred)}::${p.obj}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const topProps = deduped.slice(0, 6);

  return (
    <Card className="border-0 shadow-none w-[420px]">
      <CardHeader className="p-3 pb-1">
        <div className="flex items-center gap-1.5">
          {data.dataset && <DatasetBadge dataset={data.dataset} />}
          {data.type_hierarchy && data.type_hierarchy.length > 0 && (
            <span className="text-[10px] text-muted-foreground">
              {data.type_hierarchy.join(" › ")}
            </span>
          )}
        </div>
        <CardTitle className="text-base">{data.name}</CardTitle>
        {data.description && (
          <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
            {data.description}
          </p>
        )}
      </CardHeader>
      <CardContent className="p-3 pt-0">
        {topProps.length > 0 && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            {topProps.map((p, i) => (
              <div key={i} className="contents">
                <dt className="font-semibold text-muted-foreground">{humanizePredicate(p.pred)}</dt>
                <dd className="truncate">
                  <PropertyValue value={p.obj} />
                </dd>
              </div>
            ))}
          </dl>
        )}
        {(data.xrefs.length > 0 || (data.see_also && data.see_also.length > 0)) && (
          <div className="mt-2 pt-2 border-t text-xs text-muted-foreground flex gap-3">
            {data.xrefs.length > 0 && (
              <span>{data.xrefs.length} cross-reference{data.xrefs.length !== 1 ? "s" : ""}</span>
            )}
            {data.see_also && data.see_also.length > 0 && (
              <span>{data.see_also.length} external link{data.see_also.length !== 1 ? "s" : ""}</span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
