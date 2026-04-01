import { useQuery } from "@tanstack/react-query";
import type { EntityData } from "../lib/types";

async function fetchEntity(uri: string): Promise<EntityData> {
  const res = await fetch(`/viewer/api/entity?uri=${encodeURIComponent(uri)}`);
  if (!res.ok) throw new Error(`Entity fetch failed: ${res.status}`);
  return res.json();
}

export function useEntityQuery(uri: string, enabled: boolean) {
  return useQuery({
    queryKey: ["entity", uri],
    queryFn: () => fetchEntity(uri),
    enabled,
    staleTime: Infinity,
  });
}
