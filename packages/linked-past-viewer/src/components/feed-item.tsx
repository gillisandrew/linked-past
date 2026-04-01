import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useMemo, useState } from "react";
import { messageToMarkdown } from "../lib/markdown";
import type { ViewerMessage } from "../lib/types";
import { CopyButton } from "./copy-button";
import { DatasetBadge } from "./dataset-badge";

export function FeedItem({
  message,
  defaultOpen = true,
  subtitle,
  bookmarked = false,
  note,
  onToggleBookmark,
  onUpdateNote,
  children,
}: {
  message: ViewerMessage;
  defaultOpen?: boolean;
  subtitle?: string;
  bookmarked?: boolean;
  note?: string;
  onToggleBookmark?: () => void;
  onUpdateNote?: (text: string) => void;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [editingNote, setEditingNote] = useState(false);
  const [noteText, setNoteText] = useState(note ?? "");
  const time = new Date(message.timestamp).toLocaleTimeString();
  const markdown = useMemo(() => messageToMarkdown(message), [message]);

  function handleNoteSave() {
    onUpdateNote?.(noteText);
    setEditingNote(false);
  }

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className={`border rounded-lg mb-3 overflow-hidden ${bookmarked ? "ring-2 ring-primary/30" : ""}`}
    >
      <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 text-sm">
        <CollapsibleTrigger className="flex items-center gap-2 flex-1 min-w-0 cursor-pointer select-none hover:opacity-80">
          <span className="text-muted-foreground text-[11px] tabular-nums w-5 text-right shrink-0">
            {message.seq}
          </span>
          <span className="bg-primary text-primary-foreground px-2 py-0.5 rounded text-[11px] font-semibold uppercase shrink-0">
            {message.type}
          </span>
          {message.dataset && <DatasetBadge dataset={message.dataset} />}
          {subtitle && (
            <span className="font-semibold text-xs truncate">{subtitle}</span>
          )}
          <span className="ml-auto text-muted-foreground tabular-nums text-xs shrink-0">{time}</span>
          <span className="text-muted-foreground text-[11px] shrink-0">{open ? "collapse" : "expand"}</span>
        </CollapsibleTrigger>
        {onToggleBookmark && (
          <button
            onClick={onToggleBookmark}
            className={`text-sm cursor-pointer shrink-0 ${bookmarked ? "text-primary" : "text-muted-foreground hover:text-foreground"}`}
            title={bookmarked ? "Remove bookmark" : "Bookmark"}
          >
            {bookmarked ? "★" : "☆"}
          </button>
        )}
        <CopyButton text={markdown} label="Copy" />
      </div>
      {/* Note display / edit */}
      {(note || editingNote) && (
        <div className="px-3 py-1.5 bg-primary/5 border-b text-xs flex items-start gap-2">
          {editingNote ? (
            <>
              <input
                type="text"
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleNoteSave(); if (e.key === "Escape") setEditingNote(false); }}
                className="flex-1 bg-transparent border-b border-primary/30 outline-none text-xs py-0.5"
                placeholder="Add a note..."
                autoFocus
              />
              <button onClick={handleNoteSave} className="text-primary text-[11px] cursor-pointer">save</button>
              <button onClick={() => setEditingNote(false)} className="text-muted-foreground text-[11px] cursor-pointer">cancel</button>
            </>
          ) : (
            <>
              <span className="text-muted-foreground italic flex-1">{note}</span>
              <button
                onClick={() => { setNoteText(note ?? ""); setEditingNote(true); }}
                className="text-muted-foreground hover:text-foreground text-[11px] cursor-pointer"
              >
                edit
              </button>
            </>
          )}
        </div>
      )}
      <CollapsibleContent className="p-3">
        {children}
        {/* Add note button when no note exists */}
        {!note && !editingNote && onUpdateNote && (
          <button
            onClick={() => { setNoteText(""); setEditingNote(true); }}
            className="mt-2 text-[11px] text-muted-foreground hover:text-foreground cursor-pointer"
          >
            + Add note
          </button>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
}
