import { useState } from "react";
import { ExternalLink, ChevronDown, ChevronRight } from "lucide-react";
import { humanizePredicate } from "../lib/predicates";
import type { EntityData } from "../lib/types";
import { linkHref, shortUri } from "../lib/uri";
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
  "hasName", // duplicates the entity name shown in the header
]);

function localName(pred: string): string {
  return pred.split("/").pop()?.split("#").pop() ?? pred;
}

/** Group properties by humanized predicate label, dedup exact duplicate values. */
function groupProps(
  props: { pred: string; obj: string }[],
): { pred: string; objs: string[] }[] {
  const groups = new Map<string, { pred: string; objs: string[] }>();
  for (const p of props) {
    const label = humanizePredicate(p.pred);
    if (!groups.has(label)) {
      groups.set(label, { pred: p.pred, objs: [] });
    }
    const existing = groups.get(label)!;
    if (!existing.objs.includes(p.obj)) {
      existing.objs.push(p.obj);
    }
  }
  return Array.from(groups.values());
}

const COLLAPSE_THRESHOLD = 3;

function PropertyGroup({ group, meta }: { group: { pred: string; objs: string[] }; meta: Record<string, any> }) {
  const [expanded, setExpanded] = useState(group.objs.length <= COLLAPSE_THRESHOLD);
  const collapsible = group.objs.length > COLLAPSE_THRESHOLD;
  const visible = expanded ? group.objs : group.objs.slice(0, 1);

  return (
    <>
      {visible.map((obj, j) => (
        <div key={j} className="contents">
          <dt className="text-muted-foreground font-medium">
            {j === 0 ? (
              collapsible ? (
                <button
                  type="button"
                  onClick={() => setExpanded(!expanded)}
                  className="inline-flex items-center gap-0.5 hover:text-foreground transition-colors"
                >
                  {expanded
                    ? <ChevronDown className="w-3 h-3 shrink-0" />
                    : <ChevronRight className="w-3 h-3 shrink-0" />}
                  <PredicateLabel pred={group.pred} meta={meta[group.pred]} />
                </button>
              ) : (
                <PredicateLabel pred={group.pred} meta={meta[group.pred]} />
              )
            ) : null}
          </dt>
          <dd className="break-words">
            <PropertyValue value={obj} />
            {j === 0 && !expanded && (
              <button
                type="button"
                onClick={() => setExpanded(true)}
                className="text-xs text-muted-foreground ml-1 hover:text-foreground transition-colors"
              >
                (+{group.objs.length - 1} more)
              </button>
            )}
          </dd>
        </div>
      ))}
    </>
  );
}

export function EntityCard({ data }: { data: EntityData }) {
  const filtered = data.properties.filter(
    (p) => !HIDDEN_PREDICATES.has(localName(p.pred)),
  );
  const groups = groupProps(filtered);
  const meta = data.predicate_meta ?? {};

  return (
    <div>
      <div className="flex items-baseline gap-2 mb-1">
        {data.dataset && <DatasetBadge dataset={data.dataset} />}
        {data.type_hierarchy && data.type_hierarchy.length > 0 && (
          <span className="text-[11px] text-muted-foreground">
            {data.type_hierarchy.join(" › ")}
          </span>
        )}
      </div>
      <h3 className="text-base font-semibold tracking-tight mb-1">{data.name}</h3>
      <p className="text-xs text-muted-foreground mb-3">{shortUri(data.uri)}</p>
      {data.description && (
        <p className="text-sm text-muted-foreground leading-relaxed mb-3">
          {data.description}
        </p>
      )}

      {groups.length > 0 && (
        <dl className="grid grid-cols-[100px_1fr] gap-x-4 gap-y-1.5 text-xs mb-4">
          {groups.map((group, i) => (
            <PropertyGroup key={i} group={group} meta={meta} />
          ))}
        </dl>
      )}

      {data.see_also && data.see_also.length > 0 && (
        <div className="pt-3 border-t border-border mb-4">
          <h4 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            See also
          </h4>
          <ul className="space-y-1">
            {data.see_also.map((url, i) => (
              <li key={i} className="text-xs">
                <a
                  href={linkHref(url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  {shortUri(url)}
                  <ExternalLink className="w-3 h-3 opacity-60" />
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.xrefs.length > 0 && (
        <div className="pt-3 border-t border-border">
          <h4 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Cross-references
          </h4>
          <XrefList links={data.xrefs} />
        </div>
      )}
    </div>
  );
}
