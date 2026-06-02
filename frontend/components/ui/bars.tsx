import { colorFor } from "@/lib/format";

export interface BarRow {
  label: string;
  /** Display string for the value, e.g. "42.0%". */
  display: string;
  /** Fraction 0..1 controlling bar width. */
  fraction: number;
  /** Optional secondary line under the label. */
  sub?: string;
  /** Negative bars render in red, positive in green; default is neutral signal. */
  sign?: "neg" | "pos" | "neutral";
}

function barColor(sign: BarRow["sign"], index: number): string {
  if (sign === "neg") return "#9c3b2e";
  if (sign === "pos") return "#3f6b4f";
  return colorFor(index);
}

/** Horizontal labelled bar list — used for weights, contributors, exposures. */
export function BarList({ rows }: { rows: BarRow[] }) {
  if (!rows.length) return <p className="text-sm text-steel">No data to display.</p>;
  return (
    <div className="space-y-3">
      {rows.map((row, index) => (
        <div key={`${row.label}-${index}`} className="space-y-1">
          <div className="flex items-baseline justify-between text-sm">
            <span className="text-ink">
              {row.label}
              {row.sub && <span className="ml-2 text-xs text-steel">{row.sub}</span>}
            </span>
            <span className="tabular-nums text-steel">{row.display}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-ink/5">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.max(2, Math.min(100, row.fraction * 100))}%`,
                backgroundColor: barColor(row.sign, index),
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
