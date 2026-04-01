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

/**
 * Convert http:// URIs to https:// for external links.
 */
function toHttps(uri: string): string {
  return uri.replace(/^http:\/\//, "https://");
}

export function EntityUri({ uri, display }: { uri: string; display?: string }) {
  const dataset = datasetForUri(uri);
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useEntityQuery(uri, open);
  const isFullUri = uri.startsWith("http://") || uri.startsWith("https://");

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className="inline-flex items-center gap-1 cursor-pointer"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        {isFullUri ? (
          <a
            href={toHttps(uri)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-primary underline font-mono"
            onClick={(e) => e.stopPropagation()}
          >
            {display ?? shortUri(uri)}
          </a>
        ) : (
          <code className="text-xs text-primary underline">{display ?? shortUri(uri)}</code>
        )}
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
