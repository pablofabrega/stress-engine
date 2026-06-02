"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { usePortfolios } from "@/components/portfolio/portfolio-context";
import { Card, SectionTitle } from "@/components/ui/card";
import { BarList, type BarRow } from "@/components/ui/bars";
import { ErrorState, Spinner } from "@/components/ui/states";
import { InfoTooltip } from "@/components/ui/tooltip";
import { pct } from "@/lib/format";
import type { HoldingInput, PresetPortfolio } from "@/lib/types";

interface Row {
  ticker: string;
  quantity: string;
  costBasis: string;
}

const EMPTY_ROW: Row = { ticker: "", quantity: "", costBasis: "" };
const PRESET_NOTIONAL = 1_000_000;
const PRESET_PRICE = 100;

export default function PortfolioBuilderPage() {
  const { reload, setSelectedId } = usePortfolios();
  const presets = useApi<PresetPortfolio[]>(() => api.listPresetPortfolios(), []);

  const [name, setName] = useState("");
  const [rows, setRows] = useState<Row[]>([{ ...EMPTY_ROW }]);
  const [csvText, setCsvText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const previewRows = useMemo<BarRow[]>(() => {
    const parsed = rows
      .filter((r) => r.ticker.trim() && Number(r.quantity) > 0)
      .map((r) => ({
        ticker: r.ticker.trim().toUpperCase(),
        notional: Number(r.quantity) * (Number(r.costBasis) || 1),
      }));
    const total = parsed.reduce((acc, r) => acc + r.notional, 0);
    if (total <= 0) return [];
    return parsed
      .map((r) => ({ label: r.ticker, fraction: r.notional / total, display: pct(r.notional / total) }))
      .sort((a, b) => b.fraction - a.fraction);
  }, [rows]);

  async function afterCreate(id: string, label: string) {
    reload();
    setSelectedId(id);
    setSuccess(`Created “${label}”. It is now the active portfolio.`);
  }

  async function createFromRows() {
    setError(null);
    setSuccess(null);
    const holdings: HoldingInput[] = rows
      .filter((r) => r.ticker.trim() && Number(r.quantity) > 0)
      .map((r) => ({
        ticker: r.ticker.trim().toUpperCase(),
        quantity: Number(r.quantity),
        cost_basis: r.costBasis ? Number(r.costBasis) : null,
      }));
    if (!name.trim()) return setError("Give the portfolio a name.");
    if (!holdings.length) return setError("Add at least one holding with a positive quantity.");
    setBusy(true);
    try {
      const created = await api.createPortfolio(name.trim(), holdings);
      await afterCreate(created.id, created.name);
      setRows([{ ...EMPTY_ROW }]);
      setName("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function createFromCsv() {
    setError(null);
    setSuccess(null);
    const lines = csvText
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);
    if (!name.trim()) return setError("Give the portfolio a name.");
    if (!lines.length) return setError("Paste CSV rows of ticker,quantity[,cost_basis].");
    const start = lines[0].toLowerCase().includes("ticker") ? 1 : 0;
    const holdings: HoldingInput[] = [];
    for (const line of lines.slice(start)) {
      const [ticker, quantity, costBasis] = line.split(",").map((c) => c.trim());
      if (!ticker || !(Number(quantity) > 0)) continue;
      holdings.push({ ticker: ticker.toUpperCase(), quantity: Number(quantity), cost_basis: costBasis ? Number(costBasis) : null });
    }
    if (!holdings.length) return setError("No valid rows found. Expected ticker,quantity[,cost_basis].");
    setBusy(true);
    try {
      const created = await api.createPortfolio(name.trim(), holdings);
      await afterCreate(created.id, created.name);
      setCsvText("");
      setName("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function createFromPreset(preset: PresetPortfolio) {
    setError(null);
    setSuccess(null);
    const holdings: HoldingInput[] = Object.entries(preset.target_weights).map(([ticker, weight]) => ({
      ticker,
      quantity: Number(((weight * PRESET_NOTIONAL) / PRESET_PRICE).toFixed(6)),
      cost_basis: PRESET_PRICE,
    }));
    setBusy(true);
    try {
      const created = await api.createPortfolio(preset.name, holdings);
      await afterCreate(created.id, created.name);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function updateRow(index: number, patch: Partial<Row>) {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  return (
    <div className="space-y-8">
      <SectionTitle
        eyebrow="Builder"
        title="Construct or load a portfolio"
        description="Enter holdings manually, paste a CSV, or instantiate a preset. Weights are normalized from notional (quantity × cost basis)."
      />

      {error && <ErrorState message={error} />}
      {success && (
        <div className="rounded-2xl border border-[#3f6b4f]/30 bg-[#3f6b4f]/5 p-4 text-sm text-[#3f6b4f]">
          {success}{" "}
          <Link href="/overview" className="underline">
            Go to overview →
          </Link>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <Card>
          <div className="flex items-center justify-between">
            <h3 className="font-serif text-2xl text-ink">Manual entry</h3>
            {busy && <Spinner />}
          </div>
          <label className="mt-4 block text-sm text-steel">
            Portfolio name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. My Core Portfolio"
              className="mt-1 w-full rounded-xl border border-ink/15 bg-canvas px-3 py-2 text-ink focus:border-signal focus:outline-none"
            />
          </label>

          <div className="mt-4 space-y-2">
            <div className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2 text-xs uppercase tracking-[0.15em] text-steel">
              <span>Ticker</span>
              <span className="inline-flex items-center gap-1">
                Quantity <InfoTooltip text="Number of shares/units held. Used with cost basis to compute notional weight." />
              </span>
              <span className="inline-flex items-center gap-1">
                Cost basis <InfoTooltip text="Average price paid per unit (optional). Used to weight holdings by notional when present." />
              </span>
              <span />
            </div>
            {rows.map((row, i) => (
              <div key={i} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2">
                <input
                  value={row.ticker}
                  onChange={(e) => updateRow(i, { ticker: e.target.value })}
                  placeholder="AAPL"
                  className="rounded-xl border border-ink/15 bg-canvas px-3 py-2 text-sm uppercase text-ink focus:border-signal focus:outline-none"
                />
                <input
                  value={row.quantity}
                  onChange={(e) => updateRow(i, { quantity: e.target.value })}
                  placeholder="100"
                  inputMode="decimal"
                  className="rounded-xl border border-ink/15 bg-canvas px-3 py-2 text-sm text-ink focus:border-signal focus:outline-none"
                />
                <input
                  value={row.costBasis}
                  onChange={(e) => updateRow(i, { costBasis: e.target.value })}
                  placeholder="145.00"
                  inputMode="decimal"
                  className="rounded-xl border border-ink/15 bg-canvas px-3 py-2 text-sm text-ink focus:border-signal focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => setRows((prev) => (prev.length > 1 ? prev.filter((_, idx) => idx !== i) : prev))}
                  className="rounded-xl border border-ink/15 px-3 text-sm text-steel hover:border-[#9c3b2e] hover:text-[#9c3b2e]"
                  aria-label="Remove row"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setRows((prev) => [...prev, { ...EMPTY_ROW }])}
              className="rounded-full border border-ink/15 px-4 py-2 text-sm text-ink hover:border-signal hover:text-signal"
            >
              + Add holding
            </button>
            <button
              type="button"
              onClick={createFromRows}
              disabled={busy}
              className="rounded-full bg-ink px-4 py-2 text-sm text-white hover:bg-steel disabled:opacity-50"
            >
              Create portfolio
            </button>
          </div>

          <div className="mt-8 border-t border-ink/10 pt-6">
            <h4 className="font-serif text-xl text-ink">CSV upload</h4>
            <p className="mt-1 text-xs text-steel">Paste rows of <code>ticker,quantity,cost_basis</code> (header optional).</p>
            <textarea
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              rows={4}
              placeholder={"ticker,quantity,cost_basis\nAAPL,100,145\nMSFT,50,300"}
              className="mt-2 w-full rounded-xl border border-ink/15 bg-canvas px-3 py-2 font-mono text-xs text-ink focus:border-signal focus:outline-none"
            />
            <button
              type="button"
              onClick={createFromCsv}
              disabled={busy}
              className="mt-2 rounded-full border border-ink/15 px-4 py-2 text-sm text-ink hover:border-signal hover:text-signal disabled:opacity-50"
            >
              Create from CSV
            </button>
          </div>
        </Card>

        <div className="space-y-6">
          <Card>
            <h3 className="font-serif text-2xl text-ink">Live weight preview</h3>
            <p className="mt-1 text-xs text-steel">Nominal weights from the manual rows above.</p>
            <div className="mt-4">
              <BarList rows={previewRows} />
            </div>
          </Card>

          <Card>
            <h3 className="font-serif text-2xl text-ink">Preset portfolios</h3>
            <p className="mt-1 text-xs text-steel">One click instantiates the template as a new portfolio.</p>
            <div className="mt-4 space-y-3">
              {presets.loading && <Spinner />}
              {presets.error && <ErrorState message={presets.error} onRetry={presets.reload} />}
              {presets.data?.map((preset) => (
                <button
                  key={preset.key}
                  type="button"
                  disabled={busy}
                  onClick={() => createFromPreset(preset)}
                  className="block w-full rounded-2xl border border-ink/10 bg-canvas p-4 text-left transition-colors hover:border-signal disabled:opacity-50"
                >
                  <p className="font-medium text-ink">{preset.name}</p>
                  <p className="mt-1 text-xs leading-5 text-steel">{preset.description}</p>
                  <p className="mt-2 text-xs text-signal">{Object.keys(preset.target_weights).join(" · ")}</p>
                </button>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
