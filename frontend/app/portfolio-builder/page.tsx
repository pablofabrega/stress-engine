import { PagePlaceholder } from "@/components/ui/page-placeholder";

export default function PortfolioBuilderPage() {
  return (
    <PagePlaceholder
      eyebrow="Builder"
      title="Manual entry, CSV upload, presets, and live portfolio normalization."
      description="The builder will support ticker ingestion, holding metadata tagging, preset selection, and explainable previews of weights and exposures."
      metrics={[
        { label: "Holdings", value: "0", helper: "Ticker entry and CSV parsing arrive in Module 2." },
        { label: "Sectors", value: "N/A", helper: "Sector tagging will come from the portfolio loader." },
        { label: "Preview Beta", value: "N/A", helper: "Live factor preview depends on historical returns and Fama-French data." },
      ]}
    />
  );
}

