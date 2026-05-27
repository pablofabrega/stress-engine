import { PagePlaceholder } from "@/components/ui/page-placeholder";

export default function RecommendationsPage() {
  return (
    <PagePlaceholder
      eyebrow="Recommendations"
      title="Translate portfolio weaknesses into concrete hedge and allocation ideas."
      description="The recommendations page will tie scenario losses and structural exposures to explainable hedge suggestions, costs, and historical effectiveness."
      metrics={[
        { label: "Active Flags", value: "0", helper: "Recommendation triggers will activate once scenarios and analytics are live." },
        { label: "Hedge Ideas", value: "N/A", helper: "Each suggestion will include a step-by-step ratio calculation." },
        { label: "Severity", value: "N/A", helper: "Severity will be tied to measurable loss and concentration signals." },
      ]}
    />
  );
}

