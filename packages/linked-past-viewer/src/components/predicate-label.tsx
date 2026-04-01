import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useState } from "react";
import { humanizePredicate } from "../lib/predicates";
import type { PredicateMeta } from "../lib/types";

export function PredicateLabel({
  pred,
  meta,
}: {
  pred: string;
  meta?: PredicateMeta;
}) {
  const label = humanizePredicate(pred);
  const [open, setOpen] = useState(false);
  const hasInfo = meta && (meta.comment || meta.domain || meta.range);

  if (!hasInfo) {
    return <span className="font-semibold text-muted-foreground">{label}</span>;
  }

  return (
    <span className="font-semibold text-muted-foreground inline-flex items-center gap-1">
      {label}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          className="text-muted-foreground/50 hover:text-muted-foreground cursor-pointer text-[10px]"
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
        >
          ℹ
        </PopoverTrigger>
        <PopoverContent
          className="w-[300px] p-3 text-xs"
          side="right"
          align="start"
          sideOffset={4}
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
        >
          <div className="space-y-1.5">
            {meta.label && meta.label !== label && (
              <div className="font-semibold">{meta.label}</div>
            )}
            {meta.comment && (
              <p className="text-muted-foreground leading-relaxed">{meta.comment}</p>
            )}
            {(meta.domain || meta.range) && (
              <div className="pt-1 border-t text-[11px] text-muted-foreground space-x-3">
                {meta.domain && <span>Domain: <code className="text-foreground">{meta.domain}</code></span>}
                {meta.range && <span>Range: <code className="text-foreground">{meta.range}</code></span>}
              </div>
            )}
          </div>
        </PopoverContent>
      </Popover>
    </span>
  );
}
