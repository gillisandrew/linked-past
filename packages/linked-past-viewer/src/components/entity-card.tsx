import { ExternalLink } from "lucide-react";
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

/**
 * Deduplicate and group properties:
 * - If a predicate appears multiple times with URI values, collapse to "N items"
 * - Otherwise keep first occurrence
 */
function deduplicateProps(
  props: { pred: string; obj: string }[],
): { pred: string; obj: string; count?: number }[] {
  // Group by humanized label (catches hasName + hasPersonName both → "Name")
  const groups = new Map<string, { pred: string; objs: string[] }>();
  for (const p of props) {
    const label = humanizePredicate(p.pred);
    if (!groups.has(label)) {
      groups.set(label, { pred: p.pred, objs: [] });
    }
    // Skip exact duplicate values within the same label group
    const existing = groups.get(label)!;
    if (!existing.objs.includes(p.obj)) {
      existing.objs.push(p.obj);
    }
  }

  const result: { pred: string; obj: string; count?: number }[] = [];
  for (const [, group] of groups) {
    if (group.objs.length <= 2) {
      // Show all values for small groups
      for (const obj of group.objs) {
        result.push({ pred: group.pred, obj });
      }
    } else {
      // Show first value + count for large groups
      result.push({ pred: group.pred, obj: group.objs[0], count: group.objs.length });
    }
  }
  return result;
}

export function EntityCard({ data }: { data: EntityData }) {
  const filtered = data.properties.filter(
    (p) => !HIDDEN_PREDICATES.has(localName(p.pred)),
  );
  const visibleProps = deduplicateProps(filtered);
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

      {visibleProps.length > 0 && (
        <dl className="grid grid-cols-[100px_1fr] gap-x-4 gap-y-1.5 text-xs mb-4">
          {visibleProps.map((p, i) => (
            <div key={i} className="contents">
              <dt className="text-muted-foreground font-medium">
                <PredicateLabel pred={p.pred} meta={meta[p.pred]} />
              </dt>
              <dd className="break-words">
                <PropertyValue value={p.obj} />
                {p.count && p.count > 1 && (
                  <span className="text-xs text-muted-foreground ml-1">
                    (+{p.count - 1} more)
                  </span>
                )}
              </dd>
            </div>
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
