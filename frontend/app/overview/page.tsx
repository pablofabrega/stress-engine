"use client";

import Link from "next/link";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { RequirePortfolio } from "@/components/portfolio/require-portfolio";
import { Card, MetricCard, SectionTitle } from "@/components/ui/card";
import { BarList, type BarRow } from "@/components/ui/bars";
import { ErrorState, LoadingSkeleton, Spinner } from "@/components/ui/states";
import { AlertTriangle } from "lucide-react";
import { compactCurrency, num, pct, signedPct } from "@/lib/format";
import type { Portfolio, RiskSnapshot, ScenarioDefinition, ScenarioRun, HistoricalResult } from "@/lib/types";

export default function OverviewPage() {
  return (
    <div className="space-y-8">
      <SectionTitle
        eyebrow="Overview"
        title="Portfolio at a glance"
        description="Composition, headline risk, and one-click crisis replays for the active portfolio."
      />
      <RequirePortfolio>{(portfolio) => <OverviewBody portfolio={portfolio} />}</RequirePortfolio>
    </div>
  );
}

function OverviewBody({ portfolio }: { portfolio: Portfolio }) {
  const detail = useApi(() => api.getPortfolio(portfolio.id), [portfolio.id]);
  const risk = useApi<RiskSnapshot>(() => api.getRisk(portfolio.id), [portfolio.id]);

  const analytics = detail.data?.analytics;
  const topHoldings: BarRow[] = analytics
    ? Object.entries(analytics.holding_weights)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([ticker, w]) => ({ label: ticker, fraction: w, display: pct(w) }))
    : [];
  const sectors: BarRow[] = analytics
    ? Object.entries(analytics.sector_weights)
        .sort((a, b) => b[1] - a[1])
        .map(([sector, w]) => ({ label: sector, fraction: w, display: pct(w) }))
    : [];

  return (
    <div className="space-y-8">
      {risk.loading && <LoadingSkeleton rows={1} />}
      {risk.error && <ErrorState message={risk.error} onRetry={risk.reload} />}
      {risk.data && (
        <>
          {risk.data.warnings.length > 0 && (
            <div className="flex items-start gap-2 rounded-2xl border border-[#c08552]/40 bg-[#c08552]/10 p-4 text-sm text-[#7a4a25]">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              <div>
                <p className="font-medium">Data caveats</p>
                <ul className="mt-1 list-disc pl-5">
                  {risk.data.warnings.slice(0, 4).map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
          <div className="grid gap-4 md:grid-cols-4">
            <MetricCard
              label="VaR 95%"
              value={pct(risk.data.var_95)}
              accent="negative"
              tooltip="Value at Risk (95%): the daily loss not expected to be exceeded on 95% of days, from the empirical return distribution."
            />
            <MetricCard
              label="CVaR 95%"
              value={pct(risk.data.cvar_95)}
              accent="negative"
              tooltip="Conditional VaR (95%): the average loss on the worst 5% of days — captures tail severity, not just the threshold."
            />
            <MetricCard
              label="Max drawdown"
              value={pct(risk.data.drawdown.max_drawdown)}
              accent="negative"
              tooltip="Largest peak-to-trough decline over the lookback window."
            />
            <MetricCard
              label="Market beta"
              value={num(risk.data.factor_exposure.market_beta)}
              tooltip="Sensitivity to the market factor from a Fama-French regression. Beta > 1 amplifies market moves."
            />
          </div>
        </>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <h3 className="font-serif text-2xl text-ink">Summary</h3>
          {detail.loading && <Spinner />}
          {detail.error && <ErrorState message={detail.error} onRetry={detail.reload} />}
          {analytics && (
            <dl className="mt-4 space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-steel">Total notional</dt>
                <dd className="font-medium text-ink">{compactCurrency(analytics.total_notional)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-steel">Holdings</dt>
                <dd className="font-medium text-ink">{detail.data?.holdings.length ?? 0}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-steel">Sectors</dt>
                <dd className="font-medium text-ink">{Object.keys(analytics.sector_weights).length}</dd>
              </div>
            </dl>
          )}
        </Card>
        <Card>
          <h3 className="font-serif text-2xl text-ink">Top holdings</h3>
          <div className="mt-4">{detail.loading ? <Spinner /> : <BarList rows={topHoldings} />}</div>
        </Card>
        <Card>
          <h3 className="font-serif text-2xl text-ink">Sector weights</h3>
          <div className="mt-4">{detail.loading ? <Spinner /> : <BarList rows={sectors} />}</div>
        </Card>
      </div>

      <QuickScenarios portfolioId={portfolio.id} />
    </div>
  );
}

function QuickScenarios({ portfolioId }: { portfolioId: string }) {
  const scenarios = useApi<ScenarioDefinition[]>(() => api.listScenarios(), []);
  const historical = (scenarios.data ?? []).filter((s) => s.type === "historical" && s.source === "preset");
  const [running, setRunning] = useState<string | null>(null);
  const [runs, setRuns] = useState<Record<string, ScenarioRun>>({});
  const [error, setError] = useState<string | null>(null);

  async function run(id: string) {
    setRunning(id);
    setError(null);
    try {
      const result = await api.createScenarioRun(portfolioId, id);
      setRuns((prev) => ({ ...prev, [id]: result }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setRunning(null);
    }
  }

  return (
    <Card>
      <div className="flex items-center justify-between">
        <h3 className="font-serif text-2xl text-ink">Quick crisis replays</h3>
        <Link href="/historical-scenarios" className="text-sm text-signal hover:underline">
          Full historical analysis →
        </Link>
      </div>
      {scenarios.loading && <Spinner />}
      {error && <p className="mt-3 text-sm text-[#9c3b2e]">{error}</p>}
      <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {historical.map((s) => {
          const completed = runs[s.id];
          const result = completed?.status === "completed" ? (completed.result as HistoricalResult) : null;
          return (
            <div key={s.id} className="rounded-2xl border border-ink/10 bg-canvas p-4">
              <p className="font-medium text-ink">{s.name}</p>
              {result ? (
                <div className="mt-2 space-y-1 text-sm">
                  <p className="font-serif text-2xl text-[#9c3b2e]">{signedPct(result.summary.final_return)}</p>
                  <p className="text-xs text-steel">vs SPY {signedPct(result.summary.spy_final_return)}</p>
                  <p className="text-xs text-steel">max DD {pct(result.summary.max_drawdown)}</p>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => run(s.id)}
                  disabled={running === s.id}
                  className="mt-3 rounded-full bg-ink px-3 py-1.5 text-xs text-white hover:bg-steel disabled:opacity-50"
                >
                  {running === s.id ? "Running…" : "Run replay"}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
