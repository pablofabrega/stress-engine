import { PagePlaceholder } from "@/components/ui/page-placeholder";

export default function OverviewPage() {
  return (
    <PagePlaceholder
      eyebrow="Dashboard"
      title="Portfolio-level risk, quick stress entry points, and active alerts."
      description="This page will surface the current portfolio state, headline risk metrics, one-click crisis replays, and recommendation banners."
      metrics={[
        { label: "Total Value", value: "$0.00", helper: "Phase 1 placeholder for live market value." },
        { label: "CVaR 95", value: "N/A", helper: "Tail-loss estimate will appear once analytics are implemented." },
        { label: "Beta", value: "N/A", helper: "Portfolio beta will be computed after factor decomposition lands." },
      ]}
    />
  );
}

