import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useState } from "react";
import { useEntityQuery } from "../hooks/use-entity-query";
import { datasetForUri, shortUri } from "../lib/uri";
import { DatasetBadge } from "./dataset-badge";
import { EntityPopoverContent } from "./entity-popover";

export function EntityUri({ uri, display }: { uri: string; display?: string }) {
  const dataset = datasetForUri(uri);
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useEntityQuery(uri, open);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className="inline-flex items-center gap-1 cursor-pointer"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        <code className="text-xs text-primary underline">{display ?? shortUri(uri)}</code>
        {dataset && <DatasetBadge dataset={dataset} />}
      </PopoverTrigger>
      <PopoverContent
        className="p-0 w-auto"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        side="bottom"
        align="start"
        sideOffset={2}
      >
        {isLoading ? (
          <div className="p-4 text-sm text-muted-foreground">Loading…</div>
        ) : data ? (
          <EntityPopoverContent data={data} />
        ) : (
          <div className="p-4 text-sm text-muted-foreground">{uri}</div>
        )}
      </PopoverContent>
    </Popover>
  );
}
