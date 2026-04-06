import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  Bookmark,
  BookmarkCheck,
  ChevronRight,
  Database,
  FileText,
  Link2,
  Search,
  User,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { messageToMarkdown } from "../lib/markdown";
import type { ViewerMessage } from "../lib/types";
import { CopyButton } from "./copy-button";
import { DatasetBadge } from "./dataset-badge";

const TYPE_META: Record<string, { icon: React.ReactNode; color: string }> = {
  query: { icon: <Database className="w-3.5 h-3.5" />, color: "text-muted-foreground" },
  search: { icon: <Search className="w-3.5 h-3.5" />, color: "text-muted-foreground" },
  entity: { icon: <User className="w-3.5 h-3.5" />, color: "text-muted-foreground" },
  links: { icon: <Link2 className="w-3.5 h-3.5" />, color: "text-muted-foreground" },
  report: { icon: <FileText className="w-3.5 h-3.5" />, color: "text-muted-foreground" },
};

export function FeedItem({
  message,
  defaultOpen = true,
  forceOpen,
  subtitle,
  bookmarked = false,
  note,
  onToggleBookmark,
  onUpdateNote,
  children,
}: {
  message: ViewerMessage;
  defaultOpen?: boolean;
  forceOpen?: { value: boolean; rev: number } | null;
  subtitle?: string;
  bookmarked?: boolean;
  note?: string;
  onToggleBookmark?: () => void;
  onUpdateNote?: (text: string) => void;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  // Respond to expand all / collapse all
  useEffect(() => {
    if (forceOpen) {
      setOpen(forceOpen.value);
    }
  }, [forceOpen?.rev]); // eslint-disable-line react-hooks/exhaustive-deps
  const [editingNote, setEditingNote] = useState(false);
  const [noteText, setNoteText] = useState(note ?? "");
  const time = new Date(message.timestamp).toLocaleTimeString();
  const markdown = useMemo(() => messageToMarkdown(message), [message]);

  function handleNoteSave() {
    onUpdateNote?.(noteText);
    setEditingNote(false);
  }

  const typeMeta = TYPE_META[message.type] ?? { icon: null, color: "text-muted-foreground" };

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className={`border-b border-border ${bookmarked ? "bg-primary/[0.02]" : ""}`}
    >
      <div className="flex items-center gap-2.5 py-2.5 text-sm">
        <CollapsibleTrigger className="flex items-center gap-2 flex-1 min-w-0 cursor-pointer select-none hover:opacity-80">
          <span className="text-muted-foreground text-[11px] tabular-nums w-5 text-right shrink-0">
            {message.seq}
          </span>
          <span
            className={`shrink-0 ${typeMeta.color}`}
          >
            {typeMeta.icon}
          </span>
          {message.dataset && <DatasetBadge dataset={message.dataset} />}
          {subtitle && (
            <span className="font-semibold text-xs truncate">{subtitle}</span>
          )}
          <span className="ml-auto text-muted-foreground tabular-nums text-xs shrink-0">{time}</span>
          <span className={`text-muted-foreground shrink-0 transition-transform ${open ? "rotate-90" : ""}`}>
            <ChevronRight className="w-3 h-3" />
          </span>
        </CollapsibleTrigger>
        {onToggleBookmark && (
          <button
            onClick={onToggleBookmark}
            className={`cursor-pointer shrink-0 transition-colors ${bookmarked ? "text-primary" : "text-muted-foreground hover:text-foreground"}`}
            title={bookmarked ? "Remove bookmark" : "Bookmark"}
          >
            {bookmarked ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
          </button>
        )}
        <CopyButton text={markdown} label="Copy" />
      </div>
      {/* Note display / edit */}
      {(note || editingNote) && (
        <div className="py-1.5 pl-6 text-xs flex items-start gap-2">
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
      <CollapsibleContent className="pb-4 pl-6">
        {children}
        {/* Add note button when no note exists */}
        {!note && !editingNote && onUpdateNote && (
          <button
            onClick={() => { setNoteText(""); setEditingNote(true); }}
            className="mt-3 text-[11px] text-muted-foreground hover:text-foreground cursor-pointer"
          >
            + Add note
          </button>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
}
