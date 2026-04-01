import type { EntityData } from "../lib/types";
export function EntityCard({ data }: { data: EntityData }) {
  return <pre className="text-xs">{JSON.stringify(data, null, 2)}</pre>;
}
