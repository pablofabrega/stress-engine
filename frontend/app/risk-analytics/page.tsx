import { PagePlaceholder } from "@/components/ui/page-placeholder";

export default function RiskAnalyticsPage() {
  return (
    <PagePlaceholder
      eyebrow="Risk Analytics"
      title="Volatility, tail risk, drawdowns, concentration, and factor exposures."
      description="The analytics page will present rolling risk measures, concentration metrics, correlation matrices, and factor decomposition with explicit formulas."
      metrics={[
        { label: "VaR / CVaR", value: "N/A", helper: "Empirical tail risk metrics are planned for Module 6." },
        { label: "Max Drawdown", value: "N/A", helper: "Recovery-time logic will accompany drawdown analytics." },
        { label: "HHI", value: "N/A", helper: "Concentration metrics will quantify single-name dependence." },
      ]}
    />
  );
}

