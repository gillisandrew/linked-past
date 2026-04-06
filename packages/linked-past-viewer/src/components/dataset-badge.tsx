import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useState } from "react";
import { DATASETS } from "../lib/datasets";

const TEXT_COLORS: Record<string, string> = {
  dprr: "#60a5fa",     // blue-400
  pleiades: "#4ade80",  // green-400
  periodo: "#c084fc",   // violet-400
  nomisma: "#facc15",   // yellow-400
  crro: "#fb923c",      // orange-400
  ocre: "#f87171",      // red-400
  edh: "#22d3ee",       // cyan-400
  rpc: "#2dd4bf",       // teal-400
};

export function DatasetBadge({ dataset }: { dataset: string }) {
  const textColor = TEXT_COLORS[dataset.toLowerCase()] ?? "#a1a1aa";
  const info = DATASETS[dataset];
  const [open, setOpen] = useState(false);

  if (!info) {
    return (
      <span
        className="text-[10px] font-medium uppercase tracking-wider"
        style={{ color: textColor }}
      >
        {dataset}
      </span>
    );
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className="cursor-pointer"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        <span
          className="text-[10px] font-medium uppercase tracking-wider"
          style={{ color: textColor }}
        >
          {dataset}
        </span>
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
