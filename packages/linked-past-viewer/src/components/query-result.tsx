import type { QueryData } from "../lib/types";
export function QueryResult({ data }: { data: QueryData }) {
  return <pre className="text-xs">{JSON.stringify(data, null, 2)}</pre>;
}
