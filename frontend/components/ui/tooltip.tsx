"use client";

import { Info } from "lucide-react";
import { useState } from "react";

/**
 * Explainability tooltip — the non-negotiable "what / how / why" affordance.
 *
 * Renders a small info icon that, on hover or focus, reveals a plain-English
 * explanation of a metric and how it is calculated. Every metric in the product
 * is paired with one of these.
 */
export function InfoTooltip({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label="Explain this metric"
        className="text-steel/70 transition-colors hover:text-signal focus:text-signal focus:outline-none"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        <Info size={14} />
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-1/2 top-6 z-20 w-64 -translate-x-1/2 rounded-xl border border-ink/10 bg-ink px-3 py-2 text-xs leading-5 text-canvas shadow-panel"
        >
          {text}
        </span>
      )}
    </span>
  );
}

export function LabelWithTooltip({ label, tooltip }: { label: string; tooltip?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span>{label}</span>
      {tooltip && <InfoTooltip text={tooltip} />}
    </span>
  );
}
