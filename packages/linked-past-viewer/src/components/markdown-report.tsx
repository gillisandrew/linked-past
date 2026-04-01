import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ReportData } from "../lib/types";

export function MarkdownReport({ data }: { data: ReportData }) {
  return (
    <div>
      {data.title && <h2 className="text-lg font-semibold mb-2">{data.title}</h2>}
      <div className="prose prose-sm dark:prose-invert max-w-none">
        <Markdown
          remarkPlugins={[remarkGfm]}
          components={{
            table: ({ children }) => (
              <table className="w-full border-collapse text-sm">{children}</table>
            ),
            th: ({ children }) => (
              <th className="text-left p-1.5 border-b-2 font-semibold bg-muted/50">{children}</th>
            ),
            td: ({ children }) => (
              <td className="p-1.5 border-b">{children}</td>
            ),
          }}
        >
          {data.markdown}
        </Markdown>
      </div>
    </div>
  );
}
