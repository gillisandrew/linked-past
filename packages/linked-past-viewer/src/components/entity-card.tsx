import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { EntityData } from "../lib/types";
import { DatasetBadge } from "./dataset-badge";
import { EntityUri } from "./entity-uri";
import { XrefList } from "./xref-list";

export function EntityCard({ data }: { data: EntityData }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        {data.dataset && <DatasetBadge dataset={data.dataset} />}
        <CardTitle className="text-lg">{data.name}</CardTitle>
        <p className="text-xs text-muted-foreground font-mono">{data.uri}</p>
      </CardHeader>
      <CardContent>
        {data.properties.length > 0 && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm mb-3">
            {data.properties.map((p, i) => {
              const pred = p.pred.split("/").pop()?.split("#").pop() ?? p.pred;
              return (
                <div key={i} className="contents">
                  <dt className="font-semibold text-muted-foreground">{pred}</dt>
                  <dd className="break-words">
                    {p.obj.startsWith("http") ? <EntityUri uri={p.obj} /> : p.obj}
                  </dd>
                </div>
              );
            })}
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
