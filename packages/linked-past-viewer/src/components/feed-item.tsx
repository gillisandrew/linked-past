import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useState } from "react";
import type { ViewerMessage } from "../lib/types";
import { DatasetBadge } from "./dataset-badge";

export function FeedItem({
  message,
  defaultOpen = true,
  children,
}: {
  message: ViewerMessage;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const time = new Date(message.timestamp).toLocaleTimeString();

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="border rounded-lg mb-3 overflow-hidden">
      <CollapsibleTrigger className="flex items-center gap-2 w-full px-3 py-2 bg-muted/50 hover:bg-muted text-sm cursor-pointer select-none">
        <span className="bg-primary text-primary-foreground px-2 py-0.5 rounded text-[11px] font-semibold uppercase">
          {message.type}
        </span>
        {message.dataset && <DatasetBadge dataset={message.dataset} />}
        <span className="ml-auto text-muted-foreground tabular-nums text-xs">{time}</span>
        <span className="text-muted-foreground text-[11px]">{open ? "collapse" : "expand"}</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="p-3">
        {children}
      </CollapsibleContent>
    </Collapsible>
  );
}
