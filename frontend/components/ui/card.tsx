import type { ReactNode } from "react";
import { LabelWithTooltip } from "./tooltip";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-3xl border border-ink/10 bg-panel p-6 shadow-panel ${className}`}>{children}</div>
  );
}

export function SectionTitle({
  eyebrow,
  title,
  description,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="space-y-2">
      {eyebrow && <p className="text-xs uppercase tracking-[0.28em] text-signal">{eyebrow}</p>}
      <h2 className="font-serif text-3xl text-ink">{title}</h2>
      {description && <p className="max-w-3xl text-sm leading-7 text-steel">{description}</p>}
    </div>
  );
}

/** A single labelled metric value, with an explainability tooltip. */
export function MetricCard({
  label,
  value,
  tooltip,
  sub,
  accent,
}: {
  label: string;
  value: string;
  tooltip?: string;
  sub?: string;
  accent?: "negative" | "positive" | "neutral";
}) {
  const accentClass =
    accent === "negative" ? "text-[#9c3b2e]" : accent === "positive" ? "text-[#3f6b4f]" : "text-ink";
  return (
    <div className="rounded-3xl border border-ink/10 bg-panel p-5 shadow-panel">
      <p className="flex items-center gap-1.5 text-xs uppercase tracking-[0.18em] text-steel">
        <LabelWithTooltip label={label} tooltip={tooltip} />
      </p>
      <p className={`mt-3 font-serif text-3xl ${accentClass}`}>{value}</p>
      {sub && <p className="mt-2 text-xs text-steel">{sub}</p>}
    </div>
  );
}
