import {
  ArrowDownToLine,
  ChevronsDownUp,
  ChevronsUpDown,
  Download,
  Moon,
  Sun,
} from "lucide-react";
import { messageToMarkdown } from "../lib/markdown";
import type { ViewerMessage } from "../lib/types";

export function ExportButton({ messages, notes }: { messages: ViewerMessage[]; notes: Map<number, string> }) {
  function handleExport() {
    const parts = messages.map((msg) => {
      let md = messageToMarkdown(msg);
      const note = notes.get(msg.seq);
      if (note) md += `\n\n> **Note:** ${note}`;
      return md;
    });

    const header = `# linked-past session\n\nExported ${new Date().toLocaleString()}\n\n---\n`;
    const content = header + parts.join("\n\n---\n\n") + "\n";

    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `linked-past-session-${new Date().toISOString().slice(0, 16).replace(/:/g, "")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (messages.length === 0) return null;

  return (
    <button
      onClick={handleExport}
      className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
      title="Export session as markdown"
    >
      <Download className="w-3.5 h-3.5" />
      <span>Export</span>
    </button>
  );
}

export function ExpandCollapseButtons({ onExpandAll, onCollapseAll }: {
  onExpandAll: () => void;
  onCollapseAll: () => void;
}) {
  return (
    <span className="flex items-center gap-1">
      <button
        onClick={onExpandAll}
        className="inline-flex items-center gap-0.5 text-[11px] text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
        title="Expand all"
      >
        <ChevronsUpDown className="w-3.5 h-3.5" />
      </button>
      <span className="text-muted-foreground/50">/</span>
      <button
        onClick={onCollapseAll}
        className="inline-flex items-center gap-0.5 text-[11px] text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
        title="Collapse all"
      >
        <ChevronsDownUp className="w-3.5 h-3.5" />
      </button>
    </span>
  );
}

export function AutoScrollButton({ active, onClick }: { active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1 text-[11px] cursor-pointer transition-colors ${
        active ? "text-primary" : "text-muted-foreground hover:text-foreground"
      }`}
      title={active ? "Auto-scroll ON — click to disable" : "Auto-scroll OFF — click to enable"}
    >
      <ArrowDownToLine className="w-3.5 h-3.5" />
      <span>{active ? "auto-scroll" : "scroll"}</span>
    </button>
  );
}

export function DarkModeToggle() {
  function toggle() {
    document.documentElement.classList.toggle("dark");
  }

  return (
    <button
      onClick={toggle}
      className="text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
      title="Toggle dark mode"
    >
      <Sun className="w-3.5 h-3.5 dark:hidden" />
      <Moon className="w-3.5 h-3.5 hidden dark:block" />
    </button>
  );
}
