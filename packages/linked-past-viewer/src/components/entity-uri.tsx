import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useState } from "react";
import { useEntityQuery } from "../hooks/use-entity-query";
import { datasetForUri, linkHref, shortUri } from "../lib/uri";
import { EntityPopoverContent } from "./entity-popover";

/**
 * CSS variable names for dataset-colored pills.
 * Falls back to neutral gray for unknown datasets.
 */
function datasetStyle(dataset: string | null): React.CSSProperties {
  const ds = dataset ?? "default";
  return {
    backgroundColor: `var(--ds-${ds}-bg, var(--ds-default-bg))`,
    color: `var(--ds-${ds}-fg, var(--ds-default-fg))`,
  };
}

export function EntityUri({ uri, display }: { uri: string; display?: string }) {
  const dataset = datasetForUri(uri);
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useEntityQuery(uri, open);
  const isFullUri = uri.startsWith("http://") || uri.startsWith("https://");
  const label = display ?? shortUri(uri);

  const pill = (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium cursor-pointer transition-[filter] hover:brightness-95 dark:hover:brightness-110"
      style={datasetStyle(dataset)}
    >
      {label}
    </span>
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className="inline-flex items-center cursor-pointer"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        {isFullUri ? (
          <a
            href={linkHref(uri)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
          >
            {pill}
          </a>
        ) : (
          pill
        )}
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
