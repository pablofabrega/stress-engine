"use client";

import { useCallback, useEffect, useState } from "react";
import { Copy, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { usePortfolios } from "./portfolio-context";
import { Card } from "@/components/ui/card";
import { Spinner, ErrorState } from "@/components/ui/states";
import { InfoTooltip } from "@/components/ui/tooltip";
import { SECTORS } from "@/lib/format";
import type { HoldingInput, PortfolioDetail } from "@/lib/types";

interface EditRow {
  ticker: string;
  quantity: string;
  costBasis: string;
  sector: string;
  existing: boolean;
}

/**
 * Edit the active portfolio: rename, add/remove holdings, change quantity,
 * cost basis, and sector. Starter/template portfolios are read-only — they
 * surface a "Duplicate to edit" action that forks an editable copy.
 */
export function PortfolioEditor() {
  const { selected, reload, setSelectedId } = usePortfolios();
  const [detail, setDetail] = useState<PortfolioDetail | null>(null);
  const [name, setName] = useState("");
  const [rows, setRows] = useState<EditRow[]>([]);
  const [originalTickers, setOriginalTickers] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const selectedId = selected?.id ?? null;

  const hydrate = useCallback((d: PortfolioDetail) => {
    setDetail(d);
    setName(d.name);
    setRows(
      d.holdings.map((h) => ({
        ticker: h.ticker,
        quantity: String(h.quantity),
        costBasis: h.cost_basis != null ? String(h.cost_basis) : "",
        sector: h.sector ?? "",
        existing: true,
      })),
    );
    setOriginalTickers(d.holdings.map((h) => h.ticker.toUpperCase()));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    setMsg(null);
    api
      .getPortfolio(selectedId)
      .then((d) => active && hydrate(d))
      .catch((e) => active && setError(e instanceof ApiError ? e.message : String(e)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [selectedId, nonce, hydrate]);

  function updateRow(i: number, patch: Partial<EditRow>) {
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  async function duplicate() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const copy = await api.duplicatePortfolio(selected.id);
      reload();
      setSelectedId(copy.id);
      setMsg(`Created editable copy "${copy.name}".`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function deletePortfolio() {
    if (!selected) return;
    if (!window.confirm(`Delete "${selected.name}"? This cannot be undone.`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.deletePortfolio(selected.id);
      reload();
      setMsg(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!selected || !detail) return;
    const cleaned = rows.filter((r) => r.ticker.trim() && Number(r.quantity) > 0);
    if (rows.some((r) => r.ticker.trim() && !(Number(r.quantity) > 0))) {
      setError("Every holding needs a positive quantity.");
      return;
    }
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      if (name.trim() && name.trim() !== detail.name) {
        await api.renamePortfolio(selected.id, name.trim());
      }
      const currentTickers = new Set(cleaned.map((r) => r.ticker.trim().toUpperCase()));
      const deleted = originalTickers.filter((t) => !currentTickers.has(t));
      for (const ticker of deleted) {
        await api.deleteHolding(selected.id, ticker);
      }
      if (cleaned.length) {
        const payload: HoldingInput[] = cleaned.map((r) => ({
          ticker: r.ticker.trim().toUpperCase(),
          quantity: Number(r.quantity),
          cost_basis: r.costBasis ? Number(r.costBasis) : null,
          sector: r.sector || null,
        }));
        await api.updateHoldings(selected.id, payload);
      }
      reload();
      setNonce((n) => n + 1); // re-fetch detail to reflect resolved sectors
      setMsg("Changes saved.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!selected) {
    return (
      <Card>
        <p className="text-sm text-steel">Select or create a portfolio to edit it here.</p>
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h3 className="font-serif text-2xl text-ink">Manage current portfolio</h3>
          {selected.is_template && (
            <span className="rounded-full bg-ink/5 px-3 py-1 text-xs uppercase tracking-[0.15em] text-steel">Template</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {busy && <Spinner />}
          <button
            type="button"
            onClick={duplicate}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-full border border-ink/15 px-4 py-2 text-sm text-ink hover:border-signal hover:text-signal disabled:opacity-50"
          >
            <Copy size={14} /> Duplicate
          </button>
          {!selected.is_template && (
            <button
              type="button"
              onClick={deletePortfolio}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-full border border-ink/15 px-4 py-2 text-sm text-steel hover:border-[#9c3b2e] hover:text-[#9c3b2e] disabled:opacity-50"
            >
              <Trash2 size={14} /> Delete
            </button>
          )}
        </div>
      </div>

      {msg && <p className="mt-3 rounded-xl border border-[#3f6b4f]/30 bg-[#3f6b4f]/5 p-3 text-sm text-[#3f6b4f]">{msg}</p>}
      {error && <div className="mt-3"><ErrorState message={error} /></div>}

      {selected.is_template ? (
        <p className="mt-4 rounded-2xl border border-[#c08552]/40 bg-[#c08552]/10 p-4 text-sm text-[#7a4a25]">
          This is a starter template and is read-only. Click <strong>Duplicate</strong> to create an editable copy, then
          edit the copy freely.
        </p>
      ) : loading ? (
        <div className="mt-4"><Spinner /></div>
      ) : (
        <div className="mt-5 space-y-5">
          <label className="block max-w-md text-sm text-steel">
            Portfolio name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-xl border border-ink/15 bg-canvas px-3 py-2 text-ink focus:border-signal focus:outline-none"
            />
          </label>

          <div className="space-y-2">
            <div className="grid grid-cols-[1fr_0.7fr_0.8fr_1.1fr_auto] gap-2 text-xs uppercase tracking-[0.15em] text-steel">
              <span>Ticker</span>
              <span>Qty</span>
              <span>Cost</span>
              <span className="inline-flex items-center gap-1">
                Sector <InfoTooltip text="Auto-detect classifies by ticker (static lookup, then yfinance). Pick a sector to override." />
              </span>
              <span />
            </div>
            {rows.map((row, i) => (
              <div key={i} className="grid grid-cols-[1fr_0.7fr_0.8fr_1.1fr_auto] gap-2">
                <input
                  value={row.ticker}
                  onChange={(e) => updateRow(i, { ticker: e.target.value })}
                  disabled={row.existing}
                  placeholder="AAPL"
                  className="rounded-xl border border-ink/15 bg-canvas px-3 py-2 text-sm uppercase text-ink focus:border-signal focus:outline-none disabled:bg-ink/5 disabled:text-steel"
                />
                <input
                  value={row.quantity}
                  onChange={(e) => updateRow(i, { quantity: e.target.value })}
                  inputMode="decimal"
                  className="rounded-xl border border-ink/15 bg-canvas px-3 py-2 text-sm text-ink focus:border-signal focus:outline-none"
                />
                <input
                  value={row.costBasis}
                  onChange={(e) => updateRow(i, { costBasis: e.target.value })}
                  inputMode="decimal"
                  placeholder="—"
                  className="rounded-xl border border-ink/15 bg-canvas px-3 py-2 text-sm text-ink focus:border-signal focus:outline-none"
                />
                <select
                  value={SECTORS.includes(row.sector) ? row.sector : ""}
                  onChange={(e) => updateRow(i, { sector: e.target.value })}
                  className="rounded-xl border border-ink/15 bg-canvas px-2 py-2 text-sm text-ink focus:border-signal focus:outline-none"
                >
                  <option value="">{row.sector && !SECTORS.includes(row.sector) ? `Auto (${row.sector})` : "Auto-detect"}</option>
                  {SECTORS.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => setRows((prev) => prev.filter((_, idx) => idx !== i))}
                  className="rounded-xl border border-ink/15 px-3 text-sm text-steel hover:border-[#9c3b2e] hover:text-[#9c3b2e]"
                  aria-label="Remove holding"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() =>
                setRows((prev) => [...prev, { ticker: "", quantity: "", costBasis: "", sector: "", existing: false }])
              }
              className="rounded-full border border-ink/15 px-4 py-2 text-sm text-ink hover:border-signal hover:text-signal"
            >
              + Add holding
            </button>
            <button
              type="button"
              onClick={save}
              disabled={busy}
              className="rounded-full bg-ink px-4 py-2 text-sm text-white hover:bg-steel disabled:opacity-50"
            >
              Save changes
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
