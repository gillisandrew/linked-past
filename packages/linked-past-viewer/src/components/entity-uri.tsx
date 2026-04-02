import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ExternalLink } from "lucide-react";
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

export function EntityUri({ uri, display, showBadge = true }: { uri: string; display?: string; showBadge?: boolean }) {
  const dataset = datasetForUri(uri);
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useEntityQuery(uri, open);
  const isFullUri = uri.startsWith("http://") || uri.startsWith("https://");
  const label = display ?? shortUri(uri);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className="inline-flex items-center gap-1 cursor-pointer group"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        {isFullUri ? (
          <a
            href={toHttps(uri)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            <span className="underline underline-offset-2 decoration-primary/40">{label}</span>
            <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-60 transition-opacity shrink-0" />
          </a>
        ) : (
          <span className="text-xs text-primary underline underline-offset-2 decoration-primary/40">{label}</span>
        )}
        {showBadge && dataset && <DatasetBadge dataset={dataset} />}
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
