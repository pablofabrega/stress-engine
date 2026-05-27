import { PagePlaceholder } from "@/components/ui/page-placeholder";

export default function HypotheticalScenariosPage() {
  return (
    <PagePlaceholder
      eyebrow="Hypothetical Shock"
      title="Build reusable scenario definitions and estimate losses from macro and factor shocks."
      description="This page will host slider-driven shocks, fast live approximations, and full scenario runs with liquidity-adjusted loss estimates."
      metrics={[
        { label: "Shock Types", value: "6+", helper: "Rates, equity, VIX, oil, credit, and custom shocks are planned." },
        { label: "30-Day Path", value: "N/A", helper: "Drawdown simulation is scheduled for the hypothetical engine phase." },
        { label: "Similar Periods", value: "N/A", helper: "Historical analog matching will be added after shock modeling is in place." },
      ]}
    />
  );
}

