import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { lazy, Suspense, useState } from "react";
import { useEntityQuery } from "../hooks/use-entity-query";
import { datasetForUri, linkHref, shortUri } from "../lib/uri";
import { useIsStaticMode } from "@/lib/static-context";

// Lazy import to break circular dep: entity-popover → property-value → entity-uri
const EntityPopoverContent = lazy(() =>
  import("./entity-popover").then((m) => ({ default: m.EntityPopoverContent })),
);

function datasetStyle(dataset: string | null): React.CSSProperties {
  const ds = dataset ?? "default";
  return {
    textDecorationColor: `var(--ds-${ds}-line, var(--ds-default-line))`,
  };
}

const LINK_CLASSES =
  "cursor-pointer underline decoration-2 underline-offset-2";

export function EntityUri({ uri, display }: { uri: string; display?: string }) {
  const dataset = datasetForUri(uri);
  const isStatic = useIsStaticMode();
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useEntityQuery(uri, open);
  const label = display ?? shortUri(uri);

  const link = (
    <span className={LINK_CLASSES} style={datasetStyle(dataset)}>
      {label}
    </span>
  );

  if (isStatic) {
    return (
      <a href={linkHref(uri)} target="_blank" rel="noopener noreferrer" title={uri}>
        {link}
      </a>
    );
  }

  const isFullUri = uri.startsWith("http://") || uri.startsWith("https://");

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
            {link}
          </a>
        ) : (
          link
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
          <div className="p-4 text-sm text-muted-foreground">Loading...</div>
        ) : data ? (
          <Suspense fallback={<div className="p-4 text-sm text-muted-foreground">Loading...</div>}>
            <EntityPopoverContent data={data} />
          </Suspense>
        ) : (
          <div className="p-4 text-sm text-muted-foreground">{uri}</div>
        )}
      </PopoverContent>
    </Popover>
  );
}
