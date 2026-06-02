"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface SeriesDef {
  key: string;
  label: string;
  color: string;
}

const axisStyle = { fontSize: 11, fill: "#4f6475" };

function pctTick(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

/** Multi-series line chart. Values are treated as fractions and shown as %. */
export function MultiLineChart({
  data,
  xKey,
  series,
  height = 280,
}: {
  data: Array<Record<string, number | string>>;
  xKey: string;
  series: SeriesDef[];
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#17212b14" />
        <XAxis dataKey={xKey} tick={axisStyle} minTickGap={32} />
        <YAxis tickFormatter={pctTick} tick={axisStyle} width={48} />
        <Tooltip
          formatter={(value, name) => [`${(Number(value) * 100).toFixed(2)}%`, name]}
          contentStyle={{ borderRadius: 12, border: "1px solid #17212b1a", fontSize: 12 }}
        />
        {series.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={s.color}
            strokeWidth={2}
            dot={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Single filled drawdown/underwater area chart (values are negative fractions). */
export function DrawdownArea({
  data,
  xKey,
  dataKey,
  height = 220,
  color = "#9c3b2e",
}: {
  data: Array<Record<string, number | string>>;
  xKey: string;
  dataKey: string;
  height?: number;
  color?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.05} />
            <stop offset="100%" stopColor={color} stopOpacity={0.45} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#17212b14" />
        <XAxis dataKey={xKey} tick={axisStyle} minTickGap={32} />
        <YAxis tickFormatter={pctTick} tick={axisStyle} width={48} />
        <Tooltip
          formatter={(value) => [`${(Number(value) * 100).toFixed(2)}%`, "Drawdown"]}
          contentStyle={{ borderRadius: 12, border: "1px solid #17212b1a", fontSize: 12 }}
        />
        <Area type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} fill={`url(#grad-${dataKey})`} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function ChartLegend({ series }: { series: SeriesDef[] }) {
  return (
    <div className="flex flex-wrap gap-4 text-xs text-steel">
      {series.map((s) => (
        <span key={s.key} className="inline-flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: s.color }} />
          {s.label}
        </span>
      ))}
    </div>
  );
}
