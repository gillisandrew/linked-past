import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useMemo, useState } from "react";
import { messageToMarkdown } from "../lib/markdown";
import type { ViewerMessage } from "../lib/types";
import { CopyButton } from "./copy-button";
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
  const markdown = useMemo(() => messageToMarkdown(message), [message]);

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="border rounded-lg mb-3 overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 text-sm">
        <CollapsibleTrigger className="flex items-center gap-2 flex-1 cursor-pointer select-none hover:opacity-80">
          <span className="bg-primary text-primary-foreground px-2 py-0.5 rounded text-[11px] font-semibold uppercase">
            {message.type}
          </span>
          {message.dataset && <DatasetBadge dataset={message.dataset} />}
          <span className="ml-auto text-muted-foreground tabular-nums text-xs">{time}</span>
          <span className="text-muted-foreground text-[11px]">{open ? "collapse" : "expand"}</span>
        </CollapsibleTrigger>
        <CopyButton text={markdown} label="Copy" />
      </div>
      <CollapsibleContent className="p-3">
        {children}
      </CollapsibleContent>
    </Collapsible>
  );
}
