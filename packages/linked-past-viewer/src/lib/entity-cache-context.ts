import { createContext, useContext } from "react";
import type { EntityData } from "./schemas";

export type EntityCache = Map<string, EntityData>;

const EntityCacheContext = createContext<EntityCache>(new Map());

export const EntityCacheProvider = EntityCacheContext.Provider;

export function useEntityCache(): EntityCache {
  return useContext(EntityCacheContext);
}
