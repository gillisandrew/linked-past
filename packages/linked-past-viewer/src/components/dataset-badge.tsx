import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useState } from "react";
import { DATASETS } from "../lib/datasets";

const COLORS: Record<string, string> = {
  dprr: "bg-blue-500",
  pleiades: "bg-green-500",
  periodo: "bg-purple-500",
  nomisma: "bg-yellow-500 text-black",
  crro: "bg-orange-500",
  ocre: "bg-red-500",
  edh: "bg-cyan-500",
};

export function DatasetBadge({ dataset }: { dataset: string }) {
  const color = COLORS[dataset] ?? "bg-gray-500";
  const info = DATASETS[dataset];
  const [open, setOpen] = useState(false);

  if (!info) {
    return (
      <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold text-white ${color}`}>
        {dataset}
      </span>
    );
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold text-white cursor-pointer ${color}`}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        {dataset}
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
