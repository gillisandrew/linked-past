import type { SearchData } from "../lib/types";
export function SearchResults({ data }: { data: SearchData }) {
  return <pre className="text-xs">{JSON.stringify(data, null, 2)}</pre>;
}
