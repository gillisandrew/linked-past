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
      className="text-[11px] text-muted-foreground hover:text-foreground cursor-pointer"
      title="Export session as markdown"
    >
      Export
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
        className="text-[11px] text-muted-foreground hover:text-foreground cursor-pointer"
        title="Expand all"
      >
        expand all
      </button>
      <span className="text-muted-foreground">/</span>
      <button
        onClick={onCollapseAll}
        className="text-[11px] text-muted-foreground hover:text-foreground cursor-pointer"
        title="Collapse all"
      >
        collapse all
      </button>
    </span>
  );
}

export function DarkModeToggle() {
  function toggle() {
    document.documentElement.classList.toggle("dark");
  }

  return (
    <button
      onClick={toggle}
      className="text-[11px] text-muted-foreground hover:text-foreground cursor-pointer"
      title="Toggle dark mode"
    >
      ◐
    </button>
  );
}
