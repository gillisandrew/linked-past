import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { EntityData } from "../lib/types";
import { DatasetBadge } from "./dataset-badge";
import { PredicateLabel } from "./predicate-label";
import { PropertyValue } from "./property-value";
import { XrefList } from "./xref-list";

const HIDDEN_PREDICATES = new Set([
  "type", "rdf:type", "Class", "subClassOf", "subPropertyOf",
  "domain", "range", "equivalentClass", "equivalentProperty",
  "sameAs", "differentFrom", "disjointWith", "imports",
  "versionInfo", "isDefinedBy", "first", "rest",
  "hasID", "hasDprrID",
  "label", "prefLabel", "comment", "seeAlso",
]);

function localName(pred: string): string {
  return pred.split("/").pop()?.split("#").pop() ?? pred;
}

export function EntityCard({ data }: { data: EntityData }) {
  const visibleProps = data.properties.filter(
    (p) => !HIDDEN_PREDICATES.has(localName(p.pred)),
  );
  const meta = data.predicate_meta ?? {};

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          {data.dataset && <DatasetBadge dataset={data.dataset} />}
          {data.type_hierarchy && data.type_hierarchy.length > 0 && (
            <span className="text-[11px] text-muted-foreground">
              {data.type_hierarchy.join(" › ")}
            </span>
          )}
        </div>
        <CardTitle className="text-lg">{data.name}</CardTitle>
        <p className="text-xs text-muted-foreground font-mono">{data.uri}</p>
        {data.description && (
          <p className="text-sm text-muted-foreground leading-relaxed mt-1">
            {data.description}
          </p>
        )}
      </CardHeader>
      <CardContent>
        {visibleProps.length > 0 && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm mb-3">
            {visibleProps.map((p, i) => (
              <div key={i} className="contents">
                <dt>
                  <PredicateLabel pred={p.pred} meta={meta[p.pred]} />
                </dt>
                <dd className="break-words">
                  <PropertyValue value={p.obj} showBadge={false} />
                </dd>
              </div>
            ))}
          </dl>
        )}
        {data.see_also && data.see_also.length > 0 && (
          <div className="pt-2 border-t mb-3">
            <h4 className="text-xs font-semibold text-muted-foreground mb-1">See also</h4>
            <ul className="space-y-0.5">
              {data.see_also.map((url, i) => (
                <li key={i} className="text-xs">
                  <a
                    href={url.replace(/^http:\/\//, "https://")}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary underline font-mono"
                  >
                    {url.replace(/^https?:\/\//, "").replace(/\/$/, "")}
                  </a>
                </li>
              ))}
            </ul>
          </div>
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
