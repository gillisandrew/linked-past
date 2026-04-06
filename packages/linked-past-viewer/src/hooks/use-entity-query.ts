import { useQuery } from "@tanstack/react-query";
import type { EntityData } from "../lib/types";
import { useEntityCache } from "../lib/entity-cache-context";

export async function fetchEntity(uri: string): Promise<EntityData> {
  const res = await fetch(`/viewer/api/entity?uri=${encodeURIComponent(uri)}`);
  return res.json();
}

export function useEntityQuery(uri: string, enabled: boolean) {
  const cache = useEntityCache();
  const cached = cache.get(uri);

  return useQuery<EntityData>({
    queryKey: ["entity", uri],
    queryFn: () => fetchEntity(uri),
    staleTime: Infinity,
    enabled: enabled && !cached,
    ...(cached ? { initialData: cached } : {}),
  });
}
