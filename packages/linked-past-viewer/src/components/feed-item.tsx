import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Bookmark,
  BookmarkCheck,
  ChevronDown,
  ChevronUp,
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

const TYPE_META: Record<string, { icon: React.ReactNode; color: string; bg: string; label: string }> = {
  query: { icon: <Database className="w-3 h-3" />, color: "text-blue-600 dark:text-blue-400", bg: "bg-blue-100 dark:bg-blue-950", label: "Query" },
  search: { icon: <Search className="w-3 h-3" />, color: "text-violet-600 dark:text-violet-400", bg: "bg-violet-100 dark:bg-violet-950", label: "Search" },
  entity: { icon: <User className="w-3 h-3" />, color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-100 dark:bg-emerald-950", label: "Entity" },
  links: { icon: <Link2 className="w-3 h-3" />, color: "text-amber-600 dark:text-amber-400", bg: "bg-amber-100 dark:bg-amber-950", label: "Links" },
  report: { icon: <FileText className="w-3 h-3" />, color: "text-rose-600 dark:text-rose-400", bg: "bg-rose-100 dark:bg-rose-950", label: "Report" },
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

  const typeMeta = TYPE_META[message.type] ?? { icon: null, color: "text-muted-foreground", bg: "bg-muted", label: message.type };

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
          <Tooltip>
            <TooltipTrigger className={`shrink-0 inline-flex items-center justify-center w-5 h-5 rounded-full ${typeMeta.bg} ${typeMeta.color}`}>
              {typeMeta.icon}
            </TooltipTrigger>
            <TooltipContent side="bottom" className="text-xs">
              {typeMeta.label}
            </TooltipContent>
          </Tooltip>
          {message.dataset && <DatasetBadge dataset={message.dataset} />}
          {subtitle && (
            <span className="font-semibold text-xs truncate">{subtitle}</span>
          )}
          <span className="ml-auto text-muted-foreground tabular-nums text-xs shrink-0">{time}</span>
          <span className="text-muted-foreground shrink-0">
            {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
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
