import { PagePlaceholder } from "@/components/ui/page-placeholder";

export default function HistoricalScenariosPage() {
  return (
    <PagePlaceholder
      eyebrow="Historical Replay"
      title="Compare a portfolio against crisis windows using actual market paths."
      description="The historical scenario page will replay portfolio performance through 2008, 2020, 2022, and other preset stress periods using real daily returns."
      metrics={[
        { label: "Preset Windows", value: "4+", helper: "Exact replay windows are scaffolded and will be implemented in Module 3." },
        { label: "Worst Contributors", value: "N/A", helper: "PnL attribution will rank holdings and sectors by contribution." },
        { label: "Correlation Shift", value: "N/A", helper: "Before-vs-during heatmaps will highlight structural breakdowns." },
      ]}
    />
  );
}

