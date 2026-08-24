import React, { createContext, useContext, useState, useCallback } from "react";
import type { Strategy } from "../types";

interface StrategyContextValue {
  strategy: Strategy;
  setStrategy: (s: Strategy) => void;
  refreshKey: number;
  bumpRefresh: () => void;
}

const StrategyContext = createContext<StrategyContextValue | null>(null);

export function StrategyProvider({ children }: { children: React.ReactNode }) {
  const [strategy, setStrategyState] = useState<Strategy>(
    (localStorage.getItem("msched_strategy") as Strategy) || "cheapest"
  );
  const [refreshKey, setRefreshKey] = useState(0);

  const setStrategy = useCallback((s: Strategy) => {
    localStorage.setItem("msched_strategy", s);
    setStrategyState(s);
  }, []);

  const bumpRefresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  return (
    <StrategyContext.Provider value={{ strategy, setStrategy, refreshKey, bumpRefresh }}>
      {children}
    </StrategyContext.Provider>
  );
}

export function useStrategy() {
  const ctx = useContext(StrategyContext);
  if (!ctx) throw new Error("useStrategy must be used within StrategyProvider");
  return ctx;
}
