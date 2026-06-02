import type { CorrelationMatrix } from "@/lib/types";

function corrColor(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "#e8dfd0";
  // Map [-1, 1] onto a steel(neg) <-> signal(pos) ramp anchored at neutral cream.
  const v = Math.max(-1, Math.min(1, value));
  if (v >= 0) {
    const t = v;
    return `rgba(139, 94, 52, ${0.12 + 0.7 * t})`;
  }
  const t = -v;
  return `rgba(79, 100, 117, ${0.12 + 0.7 * t})`;
}

function shiftColor(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "#e8dfd0";
  const v = Math.max(-1, Math.min(1, value));
  if (v >= 0) return `rgba(156, 59, 46, ${0.1 + 0.85 * v})`; // widening correlation -> red
  return `rgba(63, 107, 79, ${0.1 + 0.85 * -v})`; // diversifying -> green
}

/**
 * Labelled correlation heatmap. In "shift" mode the scale diverges around zero
 * (red = correlations rose, green = fell); cells whose magnitude exceeds
 * `highlightThreshold` are ringed to flag regime-driven changes.
 */
export function CorrelationHeatmap({
  matrix,
  mode = "corr",
  highlightThreshold,
}: {
  matrix: CorrelationMatrix;
  mode?: "corr" | "shift";
  highlightThreshold?: number;
}) {
  if (!matrix.labels.length) {
    return <p className="text-sm text-steel">Not enough overlapping data to compute a correlation matrix.</p>;
  }
  const color = mode === "shift" ? shiftColor : corrColor;
  return (
    <div className="overflow-x-auto">
      <table className="border-separate border-spacing-1 text-xs">
        <thead>
          <tr>
            <th className="p-1" />
            {matrix.labels.map((label) => (
              <th key={label} className="p-1 font-medium text-steel">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.labels.map((rowLabel, i) => (
            <tr key={rowLabel}>
              <th className="p-1 text-right font-medium text-steel">{rowLabel}</th>
              {matrix.labels.map((colLabel, j) => {
                const value = matrix.matrix[i]?.[j] ?? null;
                const highlighted =
                  highlightThreshold !== undefined &&
                  value !== null &&
                  i !== j &&
                  Math.abs(value) > highlightThreshold;
                return (
                  <td
                    key={colLabel}
                    title={`${rowLabel} / ${colLabel}: ${value === null ? "n/a" : value.toFixed(2)}`}
                    className={`h-10 w-12 rounded text-center align-middle text-[11px] text-ink/80 ${
                      highlighted ? "ring-2 ring-ink" : ""
                    }`}
                    style={{ backgroundColor: color(value) }}
                  >
                    {value === null ? "" : value.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
