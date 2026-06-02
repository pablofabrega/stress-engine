"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { RequirePortfolio } from "@/components/portfolio/require-portfolio";
import { Card, MetricCard, SectionTitle } from "@/components/ui/card";
import { DrawdownArea } from "@/components/charts/charts";
import { ErrorState, Spinner } from "@/components/ui/states";
import { LabelWithTooltip } from "@/components/ui/tooltip";
import { currency, num, pct, signedPct } from "@/lib/format";
import type { HypotheticalResult, Portfolio, ScenarioDefinition, SimilarPeriod } from "@/lib/types";

type ShockType = "equity_market" | "rates" | "tech_selloff" | "vix_spike" | "oil_shock" | "hy_credit_selloff" | "custom";

const SHOCK_LABELS: Record<ShockType, string> = {
  equity_market: "Equity market %",
  rates: "Rates (bps)",
  tech_selloff: "Tech selloff %",
  vix_spike: "VIX spike",
  oil_shock: "Oil %",
  hy_credit_selloff: "HY credit (bps)",
  custom: "Custom per-ticker",
};

export default function HypotheticalScenariosPage() {
  return (
    <div className="space-y-8">
      <SectionTitle
        eyebrow="Hypothetical shock"
        title="Estimate instantaneous losses from macro and factor shocks"
        description="Shocks are applied through factor sensitivities (beta, duration, sector tags) and produce a liquidity-adjusted loss and a simulated 30-day path."
      />
      <RequirePortfolio>{(portfolio) => <HypotheticalBody portfolio={portfolio} />}</RequirePortfolio>
    </div>
  );
}

function HypotheticalBody({ portfolio }: { portfolio: Portfolio }) {
  const scenarios = useApi<ScenarioDefinition[]>(() => api.listScenarios(), []);
  const presets = (scenarios.data ?? []).filter((s) => s.type === "hypothetical" && s.source === "preset");

  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<HypotheticalResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // custom builder state
  const [shockType, setShockType] = useState<ShockType>("equity_market");
  const [magnitude, setMagnitude] = useState("-20");
  const [vixTarget, setVixTarget] = useState("40");
  const [customFactor, setCustomFactor] = useState("");

  async function runScenarioId(id: string) {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const run = await api.createScenarioRun(portfolio.id, id);
      if (run.status !== "completed") {
        setError((run.result as { error?: string })?.error ?? `Run ${run.status}`);
      } else {
        setResult(run.result as HypotheticalResult);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  function customParameters(): Record<string, number | string> {
    const m = Number(magnitude);
    switch (shockType) {
      case "equity_market":
      case "tech_selloff":
        return { scenario_type: shockType, shock: m / 100 };
      case "oil_shock":
        return { scenario_type: shockType, shock: m / 100 };
      case "rates":
        return { scenario_type: shockType, bps_change: m };
      case "hy_credit_selloff":
        return { scenario_type: shockType, spread_change_bps: m };
      case "vix_spike":
        return { scenario_type: shockType, current_vix: 18, target_vix: Number(vixTarget) };
      case "custom":
        return { scenario_type: "custom", factor: customFactor.toUpperCase(), magnitude: m / 100 };
      default:
        return { scenario_type: shockType };
    }
  }

  async function runCustom() {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const created = await api.createScenario({
        name: `Custom ${SHOCK_LABELS[shockType]}`,
        type: "hypothetical",
        parameters: customParameters(),
      });
      await runScenarioId(created.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      setRunning(false);
    }
  }

  return (
    <div className="space-y-8">
      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <Card>
          <h3 className="font-serif text-2xl text-ink">Preset shocks</h3>
          <p className="mt-1 text-xs text-steel">One-click macro scenarios.</p>
          {scenarios.loading && <Spinner />}
          {scenarios.error && <ErrorState message={scenarios.error} onRetry={scenarios.reload} />}
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {presets.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => runScenarioId(s.id)}
                className="rounded-2xl border border-ink/10 bg-canvas p-4 text-left transition-colors hover:border-signal"
              >
                <p className="font-medium text-ink">{s.name}</p>
                <p className="mt-1 text-xs text-steel">{s.description}</p>
              </button>
            ))}
          </div>
        </Card>

        <Card>
          <h3 className="font-serif text-2xl text-ink">Custom shock</h3>
          <div className="mt-4 space-y-3">
            <label className="block text-sm text-steel">
              <LabelWithTooltip label="Shock type" tooltip="Determines how the shock is applied: by beta, duration, sector tag, or directly to a ticker." />
              <select
                value={shockType}
                onChange={(e) => setShockType(e.target.value as ShockType)}
                className="mt-1 w-full rounded-xl border border-ink/15 bg-canvas px-3 py-2 text-ink focus:border-signal focus:outline-none"
              >
                {Object.entries(SHOCK_LABELS).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </select>
            </label>

            {shockType === "vix_spike" ? (
              <label className="block text-sm text-steel">
                Target VIX level
                <input
                  value={vixTarget}
                  onChange={(e) => setVixTarget(e.target.value)}
                  inputMode="decimal"
                  className="mt-1 w-full rounded-xl border border-ink/15 bg-canvas px-3 py-2 text-ink focus:border-signal focus:outline-none"
                />
              </label>
            ) : (
              <label className="block text-sm text-steel">
                {shockType === "rates" || shockType === "hy_credit_selloff" ? "Magnitude (bps)" : "Magnitude (%)"}
                <input
                  value={magnitude}
                  onChange={(e) => setMagnitude(e.target.value)}
                  inputMode="decimal"
                  className="mt-1 w-full rounded-xl border border-ink/15 bg-canvas px-3 py-2 text-ink focus:border-signal focus:outline-none"
                />
              </label>
            )}

            {shockType === "custom" && (
              <label className="block text-sm text-steel">
                Ticker to shock
                <input
                  value={customFactor}
                  onChange={(e) => setCustomFactor(e.target.value)}
                  placeholder="AAPL"
                  className="mt-1 w-full rounded-xl border border-ink/15 bg-canvas px-3 py-2 uppercase text-ink focus:border-signal focus:outline-none"
                />
              </label>
            )}

            <button
              type="button"
              onClick={runCustom}
              disabled={running}
              className="rounded-full bg-ink px-4 py-2 text-sm text-white hover:bg-steel disabled:opacity-50"
            >
              Run shock
            </button>
          </div>
        </Card>
      </div>

      {running && (
        <Card>
          <Spinner label="Applying shock and estimating losses…" />
        </Card>
      )}
      {error && <ErrorState message={error} />}
      {result && <HypotheticalResultView result={result} portfolioId={portfolio.id} />}
    </div>
  );
}

function HypotheticalResultView({ result, portfolioId }: { result: HypotheticalResult; portfolioId: string }) {
  const fb = result.factor_exposure_before;
  const fa = result.factor_exposure_after;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard label="Instant. return" value={signedPct(result.summary.instantaneous_return)} accent="negative" tooltip="Immediate portfolio return from the shock, summing each holding's factor-driven move." />
        <MetricCard label="Instant. PnL" value={currency(result.summary.instantaneous_pnl_dollars)} accent="negative" tooltip="Dollar PnL from the instantaneous shock across all holdings." />
        <MetricCard label="Liquidity-adj. loss" value={currency(result.summary.liquidity_adjusted_loss)} accent="negative" tooltip="Stressed loss after a haircut for positions that take more than 5 days to liquidate at typical participation rates." />
        <MetricCard label="Pre-shock value" value={currency(result.summary.total_pre_value)} tooltip="Total portfolio notional before the shock." />
      </div>

      {result.warnings.length > 0 && (
        <div className="rounded-2xl border border-[#c08552]/40 bg-[#c08552]/10 p-3 text-xs text-[#7a4a25]">
          {result.warnings.slice(0, 3).map((w, i) => (
            <p key={i}>{w}</p>
          ))}
        </div>
      )}

      <Card>
        <h3 className="font-serif text-2xl text-ink">
          <LabelWithTooltip label="Simulated 30-day path" tooltip="A deterministic stress path: the instantaneous shock plus a volatility-scaled extension using the portfolio's historical daily volatility." />
        </h3>
        <div className="mt-4">
          <DrawdownArea data={result.simulated_drawdown_path} xKey="day" dataKey="projected_drawdown" />
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h3 className="font-serif text-2xl text-ink">
            <LabelWithTooltip label="Holding impacts" tooltip="Per-holding shock return and dollar PnL produced by the shock." />
          </h3>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-[0.15em] text-steel">
                  <th className="py-2">Ticker</th>
                  <th className="py-2 text-right">Shock</th>
                  <th className="py-2 text-right">PnL</th>
                </tr>
              </thead>
              <tbody>
                {result.holding_impacts.map((row, i) => (
                  <tr key={i} className="border-t border-ink/5">
                    <td className="py-2 font-medium text-ink">{String(row.ticker)}</td>
                    <td className="py-2 text-right tabular-nums text-steel">{signedPct(row.shock_return as number)}</td>
                    <td className={`py-2 text-right tabular-nums ${(row.pnl_dollars as number) < 0 ? "text-[#9c3b2e]" : "text-[#3f6b4f]"}`}>
                      {currency(row.pnl_dollars as number)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <h3 className="font-serif text-2xl text-ink">
            <LabelWithTooltip label="Factor exposure shift" tooltip="Fama-French factor exposures before vs after the shock reweights the portfolio." />
          </h3>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-[0.15em] text-steel">
                  <th className="py-2">Factor</th>
                  <th className="py-2 text-right">Before</th>
                  <th className="py-2 text-right">After</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["Market beta", "market_beta"],
                  ["SMB (size)", "smb_exposure"],
                  ["HML (value)", "hml_exposure"],
                  ["R²", "r_squared"],
                ].map(([label, key]) => (
                  <tr key={key} className="border-t border-ink/5">
                    <td className="py-2 text-ink">{label}</td>
                    <td className="py-2 text-right tabular-nums text-steel">{num(fb[key])}</td>
                    <td className="py-2 text-right tabular-nums text-ink">{num(fa[key])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <Card>
        <h3 className="font-serif text-2xl text-ink">
          <LabelWithTooltip label="Liquidity profile" tooltip="Days to liquidate each position at 10/20/30% of average daily volume, with the liquidity-adjusted loss." />
        </h3>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-[0.15em] text-steel">
                <th className="py-2">Ticker</th>
                <th className="py-2 text-right">% of ADV</th>
                <th className="py-2 text-right">Days @10%</th>
                <th className="py-2 text-right">Days @20%</th>
                <th className="py-2 text-right">Liq-adj loss</th>
              </tr>
            </thead>
            <tbody>
              {result.liquidity_table.map((row, i) => (
                <tr key={i} className="border-t border-ink/5">
                  <td className="py-2 font-medium text-ink">{String(row.ticker)}</td>
                  <td className="py-2 text-right tabular-nums text-steel">{pct(row.position_pct_adv as number)}</td>
                  <td className="py-2 text-right tabular-nums text-steel">{num(row.days_to_liquidate_10pct as number, 1)}</td>
                  <td className="py-2 text-right tabular-nums text-steel">{num(row.days_to_liquidate_20pct as number, 1)}</td>
                  <td className="py-2 text-right tabular-nums text-[#9c3b2e]">{currency(row.liquidity_adjusted_loss_dollars as number)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <SimilarPeriodsCard featureVector={result.feature_vector} portfolioId={portfolioId} />
    </div>
  );
}

function SimilarPeriodsCard({ featureVector, portfolioId }: { featureVector: Record<string, number>; portfolioId: string }) {
  const similar = useApi<{ periods: SimilarPeriod[] }>(
    () => api.similarPeriods(featureVector, portfolioId, 3),
    [JSON.stringify(featureVector), portfolioId],
  );

  return (
    <Card>
      <h3 className="font-serif text-2xl text-ink">
        <LabelWithTooltip label="Most similar historical periods" tooltip="The 3 historical 30-day windows whose macro feature vector (equity, vol, rates, credit, equity-bond correlation) is closest by cosine similarity." />
      </h3>
      {similar.loading && <div className="mt-4"><Spinner /></div>}
      {similar.error && <div className="mt-4"><ErrorState message={similar.error} onRetry={similar.reload} /></div>}
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        {similar.data?.periods.map((p, i) => (
          <div key={i} className="rounded-2xl border border-ink/10 bg-canvas p-4">
            <p className="text-sm font-medium text-ink">
              {p.start_date} → {p.end_date}
            </p>
            <p className="mt-1 text-xs text-signal">similarity {num(p.similarity_score, 2)}</p>
            {p.portfolio_return !== null && (
              <p className="mt-1 text-xs text-steel">portfolio {signedPct(p.portfolio_return)}</p>
            )}
            <p className="mt-2 text-xs leading-5 text-steel">{p.outcome_narrative}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}
