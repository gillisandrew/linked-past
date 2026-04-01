import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { EntityData } from "../lib/types";
import { DatasetBadge } from "./dataset-badge";

/**
 * OWL/RDF/RDFS meta-predicates to hide from popovers.
 * These are structural, not human-readable.
 */
const HIDDEN_PREDICATES = new Set([
  "type",
  "rdf:type",
  "Class",
  "subClassOf",
  "subPropertyOf",
  "domain",
  "range",
  "equivalentClass",
  "equivalentProperty",
  "intersectionOf",
  "unionOf",
  "complementOf",
  "oneOf",
  "onProperty",
  "allValuesFrom",
  "someValuesFrom",
  "hasValue",
  "minCardinality",
  "maxCardinality",
  "cardinality",
  "inverseOf",
  "first",
  "rest",
  "sameAs",
  "differentFrom",
  "disjointWith",
  "distinctMembers",
  "imports",
  "versionInfo",
  "priorVersion",
  "backwardCompatibleWith",
  "incompatibleWith",
  "isDefinedBy",
]);

function localName(pred: string): string {
  return pred.split("/").pop()?.split("#").pop() ?? pred;
}

export function EntityPopoverContent({ data }: { data: EntityData }) {
  const humanProps = data.properties.filter(
    (p) => !HIDDEN_PREDICATES.has(localName(p.pred)),
  );
  const topProps = humanProps.slice(0, 5);

  return (
    <Card className="border-0 shadow-none w-[320px]">
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
          <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-xs">
            {topProps.map((p, i) => (
              <div key={i} className="contents">
                <dt className="font-semibold text-muted-foreground">{localName(p.pred)}</dt>
                <dd className="truncate">{p.obj}</dd>
              </div>
            ))}
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
