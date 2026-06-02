"use client";

import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { RequirePortfolio } from "@/components/portfolio/require-portfolio";
import { Card, SectionTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/ui/states";
import { num, pct, severityColor } from "@/lib/format";
import type { Portfolio, Recommendations, HedgeSuggestion } from "@/lib/types";

export default function RecommendationsPage() {
  return (
    <div className="space-y-8">
      <SectionTitle
        eyebrow="Recommendations"
        title="Explainable hedge suggestions"
        description="Each suggestion cites the specific portfolio weakness it addresses and shows the hedge-ratio math step by step."
      />
      <RequirePortfolio>{(portfolio) => <RecommendationsBody portfolio={portfolio} />}</RequirePortfolio>
    </div>
  );
}

function RecommendationsBody({ portfolio }: { portfolio: Portfolio }) {
  const recs = useApi<Recommendations>(() => api.getRecommendations(portfolio.id), [portfolio.id]);

  if (recs.loading) return <LoadingSkeleton rows={3} />;
  if (recs.error) return <ErrorState message={recs.error} onRetry={recs.reload} />;
  if (!recs.data?.suggestions.length)
    return (
      <EmptyState
        title="No hedges flagged"
        hint="The current portfolio did not trip any hedge triggers (high beta, duration, tech concentration, credit risk, or elevated CVaR)."
      />
    );

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {recs.data.suggestions.map((s, i) => (
        <SuggestionCard key={i} suggestion={s} />
      ))}
    </div>
  );
}

function SuggestionCard({ suggestion: s }: { suggestion: HedgeSuggestion }) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-steel">Hedge instrument</p>
          <h3 className="font-serif text-3xl text-ink">{s.instrument}</h3>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${severityColor(s.severity)}`}>{s.severity}</span>
      </div>

      <p className="mt-4 text-sm leading-7 text-ink">{s.rationale}</p>

      <div className="mt-4 rounded-2xl border border-ink/10 bg-canvas p-4">
        <p className="text-xs uppercase tracking-[0.15em] text-steel">Weakness addressed</p>
        <p className="mt-1 text-sm text-ink">{s.weakness_citation}</p>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-xs uppercase tracking-[0.15em] text-steel">Hedge ratio</p>
          <p className="mt-1 font-serif text-2xl text-ink">{num(s.hedge_ratio, 2)}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.15em] text-steel">Est. annual cost</p>
          <p className="mt-1 font-serif text-2xl text-ink">{num(s.estimated_annual_cost_bps, 0)} bps</p>
        </div>
      </div>

      {s.historical_effectiveness !== null && (
        <p className="mt-3 text-xs text-steel">
          Historical effectiveness: offsets ~{pct(s.historical_effectiveness)} of the stress loss in the cited window.
        </p>
      )}

      {s.hedge_ratio_steps.length > 0 && (
        <details className="mt-4 rounded-2xl border border-ink/10 bg-panel p-4">
          <summary className="cursor-pointer text-sm font-medium text-signal">Show hedge-ratio calculation</summary>
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-xs leading-6 text-steel">
            {s.hedge_ratio_steps.map((step, i) => (
              <li key={i} className="font-mono">
                {step}
              </li>
            ))}
          </ol>
        </details>
      )}
    </Card>
  );
}
