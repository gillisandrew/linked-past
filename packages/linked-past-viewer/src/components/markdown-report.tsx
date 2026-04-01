import type { ReportData } from "../lib/types";
export function MarkdownReport({ data }: { data: ReportData }) {
  return <pre className="text-xs">{data.markdown}</pre>;
}
