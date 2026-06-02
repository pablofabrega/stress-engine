"use client";

import { useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { RequirePortfolio } from "@/components/portfolio/require-portfolio";
import { Card, SectionTitle, MetricCard } from "@/components/ui/card";
import { CorrelationHeatmap } from "@/components/ui/heatmap";
import { ChartLegend, DrawdownArea, MultiLineChart, type SeriesDef } from "@/components/charts/charts";
import { ErrorState, Spinner } from "@/components/ui/states";
import { LabelWithTooltip } from "@/components/ui/tooltip";
import { currency, pct, signedPct } from "@/lib/format";
import type { HistoricalResult, Portfolio, ScenarioDefinition } from "@/lib/types";

const SERIES: SeriesDef[] = [
  { key: "portfolio", label: "Portfolio", color: "#8b5e34" },
  { key: "spy", label: "SPY", color: "#4f6475" },
  { key: "benchmark", label: "60/40", color: "#6b8f71" },
];

export default function HistoricalScenariosPage() {
  return (
    <div className="space-y-8">
      <SectionTitle
        eyebrow="Historical replay"
        title="Stress the portfolio through real crisis windows"
        description="Replays current holdings through actual daily returns — no rebalancing inside the window — and attributes the loss."
      />
      <RequirePortfolio>{(portfolio) => <HistoricalBody portfolio={portfolio} />}</RequirePortfolio>
    </div>
  );
}

function HistoricalBody({ portfolio }: { portfolio: Portfolio }) {
  const scenarios = useApi<ScenarioDefinition[]>(() => api.listScenarios(), []);
  const historical = (scenarios.data ?? []).filter((s) => s.type === "historical" && s.source === "preset");

  const [selected, setSelected] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<HistoricalResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(id: string) {
    setSelected(id);
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const runResult = await api.createScenarioRun(portfolio.id, id);
      if (runResult.status !== "completed") {
        const err = (runResult.result as { error?: string })?.error;
        setError(err ?? `Run ${runResult.status}`);
      } else {
        setResult(runResult.result as HistoricalResult);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-8">
      {scenarios.loading && <Spinner />}
      {scenarios.error && <ErrorState message={scenarios.error} onRetry={scenarios.reload} />}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        {historical.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => run(s.id)}
            className={`rounded-2xl border p-4 text-left transition-colors ${
              selected === s.id ? "border-signal bg-panel" : "border-ink/10 bg-canvas hover:border-signal"
            }`}
          >
            <p className="font-medium text-ink">{s.name}</p>
            <p className="mt-1 text-xs text-steel">
              {s.start_date} → {s.end_date}
            </p>
          </button>
        ))}
      </div>

      {running && (
        <Card>
          <Spinner label="Replaying scenario against real market data…" />
        </Card>
      )}
      {error && <ErrorState message={error} onRetry={selected ? () => run(selected) : undefined} />}
      {result && <HistoricalResultView result={result} />}
    </div>
  );
}

function HistoricalResultView({ result }: { result: HistoricalResult }) {
  const chartData = useMemo(() => {
    const comp = new Map<string, Record<string, number | string>>();
    for (const row of result.comparison_path) comp.set(String(row.date), row);
    return result.portfolio_path.map((row) => {
      const c = comp.get(String(row.date)) ?? {};
      return {
        date: String(row.date),
        portfolio: row.cumulative_return as number,
        spy: c.spy_cumulative_return as number,
        benchmark: c.benchmark_60_40_cumulative_return as number,
      };
    });
  }, [result]);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard label="Portfolio return" value={signedPct(result.summary.final_return)} accent="negative" tooltip="Cumulative portfolio return over the scenario window using realized daily returns." />
        <MetricCard label="vs SPY" value={signedPct(result.summary.spy_final_return)} tooltip="Cumulative SPY return over the same window for comparison." />
        <MetricCard label="vs 60/40" value={signedPct(result.summary.benchmark_final_return)} tooltip="Cumulative return of a 60% SPY / 40% BND benchmark over the window." />
        <MetricCard label="Max drawdown" value={pct(result.summary.max_drawdown)} accent="negative" tooltip="Largest peak-to-trough decline within the scenario window." />
      </div>

      {result.warnings.length > 0 && (
        <div className="rounded-2xl border border-[#c08552]/40 bg-[#c08552]/10 p-3 text-xs text-[#7a4a25]">
          {result.warnings.slice(0, 3).map((w, i) => (
            <p key={i}>{w}</p>
          ))}
        </div>
      )}

      <Card>
        <div className="flex items-center justify-between">
          <h3 className="font-serif text-2xl text-ink">
            <LabelWithTooltip label="Cumulative return path" tooltip="Portfolio cumulative return vs SPY and a 60/40 benchmark, day by day through the crisis." />
          </h3>
          <ChartLegend series={SERIES} />
        </div>
        <div className="mt-4">
          <MultiLineChart data={chartData} xKey="date" series={SERIES} />
        </div>
      </Card>

      <Card>
        <h3 className="font-serif text-2xl text-ink">
          <LabelWithTooltip label="Drawdown (underwater)" tooltip="Cumulative decline from the running peak — how deep the portfolio was below its high-water mark." />
        </h3>
        <div className="mt-4">
          <DrawdownArea data={result.portfolio_path} xKey="date" dataKey="drawdown" />
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <ContributorTable title="Worst contributors" tooltip="Holdings with the most negative PnL during the scenario." rows={result.worst_contributors} />
        <ContributorTable title="Best contributors" tooltip="Holdings that gained or lost least during the scenario." rows={result.best_contributors} />
      </div>

      <Card>
        <h3 className="font-serif text-2xl text-ink">
          <LabelWithTooltip label="Loss by sector" tooltip="Share of total scenario PnL attributable to each sector." />
        </h3>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-[0.15em] text-steel">
                <th className="py-2">Sector</th>
                <th className="py-2 text-right">PnL</th>
                <th className="py-2 text-right">% of total</th>
              </tr>
            </thead>
            <tbody>
              {result.sector_breakdown.map((row, i) => (
                <tr key={i} className="border-t border-ink/5">
                  <td className="py-2 text-ink">{String(row.sector)}</td>
                  <td className="py-2 text-right tabular-nums text-[#9c3b2e]">{currency(row.pnl_dollars as number)}</td>
                  <td className="py-2 text-right tabular-nums text-steel">{pct(row.contribution_pct_of_total_pnl as number)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <h4 className="font-serif text-xl text-ink">
            <LabelWithTooltip label="Correlation before" tooltip="Pairwise correlations in the window just before the crisis began." />
          </h4>
          <div className="mt-4">
            <CorrelationHeatmap matrix={result.correlation_before} mode="corr" />
          </div>
        </Card>
        <Card>
          <h4 className="font-serif text-xl text-ink">
            <LabelWithTooltip label="Correlation during" tooltip="Pairwise correlations during the crisis window — diversification often breaks down here." />
          </h4>
          <div className="mt-4">
            <CorrelationHeatmap matrix={result.correlation_during} mode="corr" />
          </div>
        </Card>
        <Card>
          <h4 className="font-serif text-xl text-ink">
            <LabelWithTooltip label="Correlation shift" tooltip="During minus before. Red = correlations rose (less diversification); ringed cells shifted by more than 0.2." />
          </h4>
          <div className="mt-4">
            <CorrelationHeatmap matrix={result.correlation_shift} mode="shift" highlightThreshold={0.2} />
          </div>
        </Card>
      </div>
    </div>
  );
}

function ContributorTable({
  title,
  tooltip,
  rows,
}: {
  title: string;
  tooltip: string;
  rows: Array<Record<string, number | string>>;
}) {
  return (
    <Card>
      <h3 className="font-serif text-2xl text-ink">
        <LabelWithTooltip label={title} tooltip={tooltip} />
      </h3>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-[0.15em] text-steel">
              <th className="py-2">Ticker</th>
              <th className="py-2">Sector</th>
              <th className="py-2 text-right">PnL</th>
              <th className="py-2 text-right">% of total</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-t border-ink/5">
                <td className="py-2 font-medium text-ink">{String(row.ticker)}</td>
                <td className="py-2 text-steel">{String(row.sector)}</td>
                <td className={`py-2 text-right tabular-nums ${(row.pnl_dollars as number) < 0 ? "text-[#9c3b2e]" : "text-[#3f6b4f]"}`}>
                  {currency(row.pnl_dollars as number)}
                </td>
                <td className="py-2 text-right tabular-nums text-steel">{pct(row.contribution_pct_of_total_pnl as number)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
