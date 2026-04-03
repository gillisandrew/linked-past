import { createContext, useContext } from "react";

const StaticModeContext = createContext(false);

export const StaticModeProvider = StaticModeContext.Provider;

export function useIsStaticMode(): boolean {
  return useContext(StaticModeContext);
}
