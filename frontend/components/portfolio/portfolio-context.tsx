"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import type { Portfolio } from "@/lib/types";

interface PortfolioContextValue {
  portfolios: Portfolio[];
  selectedId: string | null;
  selected: Portfolio | null;
  setSelectedId: (id: string) => void;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

const PortfolioContext = createContext<PortfolioContextValue | null>(null);
const STORAGE_KEY = "stress-workbench:selected-portfolio";

export function PortfolioProvider({ children }: { children: ReactNode }) {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedId, setSelectedIdState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const setSelectedId = useCallback((id: string) => {
    setSelectedIdState(id);
    try {
      window.localStorage.setItem(STORAGE_KEY, id);
    } catch {
      /* localStorage unavailable (SSR / private mode) — ignore */
    }
  }, []);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    api
      .listPortfolios()
      .then((list) => {
        if (!active) return;
        setPortfolios(list);
        const stored = (() => {
          try {
            return window.localStorage.getItem(STORAGE_KEY);
          } catch {
            return null;
          }
        })();
        const validStored = stored && list.some((p) => p.id === stored) ? stored : null;
        setSelectedIdState(validStored ?? list[0]?.id ?? null);
      })
      .catch((err) => active && setError(err?.message ?? "Failed to load portfolios"))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [nonce]);

  const value = useMemo<PortfolioContextValue>(
    () => ({
      portfolios,
      selectedId,
      selected: portfolios.find((p) => p.id === selectedId) ?? null,
      setSelectedId,
      loading,
      error,
      reload,
    }),
    [portfolios, selectedId, setSelectedId, loading, error, reload],
  );

  return <PortfolioContext.Provider value={value}>{children}</PortfolioContext.Provider>;
}

export function usePortfolios(): PortfolioContextValue {
  const ctx = useContext(PortfolioContext);
  if (!ctx) throw new Error("usePortfolios must be used within a PortfolioProvider");
  return ctx;
}

/** Header dropdown for choosing the active portfolio shared across pages. */
export function PortfolioSelector() {
  const { portfolios, selectedId, setSelectedId, loading } = usePortfolios();

  if (loading) return <span className="text-xs text-steel">Loading portfolios…</span>;
  if (!portfolios.length)
    return <span className="text-xs text-steel">No portfolios yet — create one in the builder.</span>;

  return (
    <label className="flex items-center gap-2 text-xs text-steel">
      <span className="uppercase tracking-[0.18em]">Portfolio</span>
      <select
        value={selectedId ?? ""}
        onChange={(e) => setSelectedId(e.target.value)}
        className="rounded-full border border-ink/15 bg-panel px-3 py-1.5 text-sm text-ink focus:border-signal focus:outline-none"
      >
        {portfolios.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
    </label>
  );
}
