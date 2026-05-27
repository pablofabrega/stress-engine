import { PagePlaceholder } from "@/components/ui/page-placeholder";

export default function SettingsPage() {
  return (
    <PagePlaceholder
      eyebrow="Settings"
      title="Provider configuration, freshness checks, and cache controls."
      description="This page will expose market data source status, cache freshness warnings, and environment-driven provider toggles for local development."
      metrics={[
        { label: "Provider", value: "yfinance", helper: "Development fallback provider from environment configuration." },
        { label: "Freshness", value: "N/A", helper: "Last successful fetch timestamps will appear here." },
        { label: "Cache State", value: "Scaffolded", helper: "Redis and parquet cache interfaces are prepared for later phases." },
      ]}
    />
  );
}
