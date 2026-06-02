"use client";

import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { RequirePortfolio } from "@/components/portfolio/require-portfolio";
import { Card, MetricCard, SectionTitle } from "@/components/ui/card";
import { ErrorState, LoadingSkeleton } from "@/components/ui/states";
import { LabelWithTooltip } from "@/components/ui/tooltip";
import { num, pct } from "@/lib/format";
import type { Portfolio, RiskSnapshot } from "@/lib/types";

export default function RiskAnalyticsPage() {
  return (
    <div className="space-y-8">
      <SectionTitle
        eyebrow="Risk analytics"
        title="Tail risk, drawdown, concentration, and factor exposures"
        description="Computed from the portfolio's daily return history over the lookback window. Every metric is empirical and explainable."
      />
      <RequirePortfolio>{(portfolio) => <RiskBody portfolio={portfolio} />}</RequirePortfolio>
    </div>
  );
}

function RiskBody({ portfolio }: { portfolio: Portfolio }) {
  const risk = useApi<RiskSnapshot>(() => api.getRisk(portfolio.id), [portfolio.id]);

  if (risk.loading) return <LoadingSkeleton rows={2} />;
  if (risk.error) return <ErrorState message={risk.error} onRetry={risk.reload} />;
  if (!risk.data) return null;
  const r = risk.data;
  const f = r.factor_exposure;

  const factorRows: Array<[string, number, number, string]> = [
    ["Alpha (daily)", r.factor_exposure.alpha, f.alpha_t_stat, "Average daily return unexplained by the factors. Significant only if |t| > ~2."],
    ["Market beta", f.market_beta, f.market_beta_t_stat, "Sensitivity to the market factor. >1 amplifies market moves."],
    ["SMB (size)", f.smb_exposure, f.smb_t_stat, "Tilt toward small caps (positive) vs large caps (negative)."],
    ["HML (value)", f.hml_exposure, f.hml_t_stat, "Tilt toward value (positive) vs growth (negative)."],
  ];

  return (
    <div className="space-y-8">
      <p className="text-xs text-steel">
        Lookback window: {r.start_date} → {r.end_date}
      </p>

      {r.warnings.length > 0 && (
        <div className="rounded-2xl border border-[#c08552]/40 bg-[#c08552]/10 p-3 text-xs text-[#7a4a25]">
          {r.warnings.slice(0, 4).map((w, i) => (
            <p key={i}>{w}</p>
          ))}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard label="VaR 95%" value={pct(r.var_95)} accent="negative" tooltip="The daily loss not expected to be exceeded on 95% of days, from the empirical (historical) return distribution." />
        <MetricCard label="VaR 99%" value={pct(r.var_99)} accent="negative" tooltip="The daily loss not expected to be exceeded on 99% of days — a more extreme threshold." />
        <MetricCard label="CVaR 95%" value={pct(r.cvar_95)} accent="negative" tooltip="Average loss on the worst 5% of days. Measures tail severity beyond the VaR threshold." />
        <MetricCard label="Realized vol" value={pct(r.rolling_vol)} tooltip="Annualized standard deviation of daily returns over the trailing window." />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h3 className="font-serif text-2xl text-ink">
            <LabelWithTooltip label="Drawdown" tooltip="Largest peak-to-trough decline, with the dates and recovery time if the portfolio regained its prior peak." />
          </h3>
          <dl className="mt-4 space-y-3 text-sm">
            <Row label="Max drawdown" value={pct(r.drawdown.max_drawdown)} negative />
            <Row label="Peak date" value={r.drawdown.peak_date ?? "—"} />
            <Row label="Trough date" value={r.drawdown.trough_date ?? "—"} />
            <Row label="Recovery date" value={r.drawdown.recovery_date ?? "not recovered"} />
            <Row label="Recovery (trading days)" value={r.drawdown.recovery_periods?.toString() ?? "—"} />
          </dl>
        </Card>

        <Card>
          <h3 className="font-serif text-2xl text-ink">
            <LabelWithTooltip label="Concentration" tooltip="How dependent the portfolio is on a few positions. HHI is the sum of squared weights (1 = single name, lower = more diversified)." />
          </h3>
          <div className="mt-4 space-y-4">
            <div>
              <div className="flex justify-between text-sm">
                <span className="text-steel">Herfindahl-Hirschman Index</span>
                <span className="font-medium text-ink">{num(r.concentration.hhi, 3)}</span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-ink/5">
                <div className="h-full rounded-full bg-signal" style={{ width: `${Math.min(100, r.concentration.hhi * 100)}%` }} />
              </div>
            </div>
            <Row label="Top-3 weight" value={pct(r.concentration.top_3_weight)} />
            <Row label="Top-5 weight" value={pct(r.concentration.top_5_weight)} />
          </div>
        </Card>
      </div>

      <Card>
        <h3 className="font-serif text-2xl text-ink">
          <LabelWithTooltip label="Fama-French factor exposures" tooltip="OLS regression of portfolio excess returns on the market, size (SMB), and value (HML) factors. t-stats indicate significance; R² is variance explained." />
        </h3>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-[0.15em] text-steel">
                <th className="py-2">Factor</th>
                <th className="py-2 text-right">Exposure</th>
                <th className="py-2 text-right">t-stat</th>
                <th className="py-2 text-right">Significant?</th>
              </tr>
            </thead>
            <tbody>
              {factorRows.map(([label, exposure, tstat, tip]) => (
                <tr key={label} className="border-t border-ink/5">
                  <td className="py-2 text-ink">
                    <LabelWithTooltip label={label} tooltip={tip} />
                  </td>
                  <td className="py-2 text-right tabular-nums text-ink">{num(exposure, 3)}</td>
                  <td className="py-2 text-right tabular-nums text-steel">{num(tstat, 2)}</td>
                  <td className="py-2 text-right text-xs">
                    {Math.abs(tstat) > 2 ? (
                      <span className="rounded-full bg-[#3f6b4f]/15 px-2 py-0.5 text-[#3f6b4f]">yes</span>
                    ) : (
                      <span className="rounded-full bg-ink/5 px-2 py-0.5 text-steel">no</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-steel">
            R² = {num(f.r_squared, 3)} · {f.observations} observations
          </p>
        </div>
      </Card>
    </div>
  );
}

function Row({ label, value, negative }: { label: string; value: string; negative?: boolean }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-steel">{label}</span>
      <span className={`font-medium ${negative ? "text-[#9c3b2e]" : "text-ink"}`}>{value}</span>
    </div>
  );
}
