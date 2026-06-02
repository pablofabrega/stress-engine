// Small, dependency-free formatting helpers shared across pages.

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function signedPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const formatted = `${(value * 100).toFixed(digits)}%`;
  return value > 0 ? `+${formatted}` : formatted;
}

export function currency(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: digits });
}

export function num(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function compactCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  });
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return value;
}

// Deterministic palette for sectors / categories in charts.
export const PALETTE = [
  "#8b5e34",
  "#4f6475",
  "#17212b",
  "#a98467",
  "#6b8f71",
  "#9c6b4f",
  "#3d5a6c",
  "#c08552",
  "#5c7457",
  "#7d6b91",
];

export function colorFor(index: number): string {
  return PALETTE[index % PALETTE.length];
}

export function severityColor(severity: string): string {
  switch (severity.toLowerCase()) {
    case "high":
      return "bg-[#9c3b2e] text-white";
    case "medium":
      return "bg-[#c08552] text-white";
    default:
      return "bg-[#6b8f71] text-white";
  }
}
