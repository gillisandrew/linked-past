import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { humanizePredicate } from "../lib/predicates";
import type { EntityData } from "../lib/types";
import { DatasetBadge } from "./dataset-badge";
import { PropertyValue } from "./property-value";
import { XrefList } from "./xref-list";

const HIDDEN_PREDICATES = new Set([
  "type", "rdf:type", "Class", "subClassOf", "subPropertyOf",
  "domain", "range", "equivalentClass", "equivalentProperty",
  "sameAs", "differentFrom", "disjointWith", "imports",
  "versionInfo", "isDefinedBy", "first", "rest",
  "hasID", "hasDprrID",
]);

function localName(pred: string): string {
  return pred.split("/").pop()?.split("#").pop() ?? pred;
}

export function EntityCard({ data }: { data: EntityData }) {
  const visibleProps = data.properties.filter(
    (p) => !HIDDEN_PREDICATES.has(localName(p.pred)),
  );

  return (
    <Card>
      <CardHeader className="pb-2">
        {data.dataset && <DatasetBadge dataset={data.dataset} />}
        <CardTitle className="text-lg">{data.name}</CardTitle>
        <p className="text-xs text-muted-foreground font-mono">{data.uri}</p>
      </CardHeader>
      <CardContent>
        {visibleProps.length > 0 && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm mb-3">
            {visibleProps.map((p, i) => (
              <div key={i} className="contents">
                <dt className="font-semibold text-muted-foreground">{humanizePredicate(p.pred)}</dt>
                <dd className="break-words">
                  <PropertyValue value={p.obj} />
                </dd>
              </div>
            ))}
          </dl>
        )}
        {data.xrefs.length > 0 && (
          <div className="pt-2 border-t">
            <h4 className="text-xs font-semibold text-muted-foreground mb-1">Cross-references</h4>
            <XrefList links={data.xrefs} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
