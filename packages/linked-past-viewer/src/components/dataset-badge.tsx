import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useState } from "react";
import { DATASETS } from "../lib/datasets";

function barColor(dataset: string): string {
  const ds = dataset.toLowerCase();
  return `var(--ds-${ds}-line, var(--ds-default-line))`;
}

const BADGE_CLASSES =
  "inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground leading-none";

export function DatasetBadge({ dataset }: { dataset: string }) {
  const info = DATASETS[dataset];
  const [open, setOpen] = useState(false);

  const badge = (
    <span className={BADGE_CLASSES}>
      <span
        className="w-0.5 h-2.5 rounded-full shrink-0"
        style={{ backgroundColor: barColor(dataset) }}
      />
      {dataset}
    </span>
  );

  if (!info) {
    return badge;
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className="cursor-pointer"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        {badge}
      </PopoverTrigger>
      <PopoverContent
        className="w-[280px] p-3"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        side="bottom"
        align="start"
        sideOffset={4}
      >
        <div className="space-y-1.5">
          <div className="font-semibold text-sm">{info.name}</div>
          <p className="text-xs text-muted-foreground">{info.description}</p>
          <div className="flex items-center gap-3 text-[11px] text-muted-foreground pt-1">
            <span>{info.license}</span>
            <a
              href={info.url.replace(/^http:\/\//, "https://")}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline"
              onClick={(e) => e.stopPropagation()}
            >
              {info.url.replace(/^https?:\/\//, "")}
            </a>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
