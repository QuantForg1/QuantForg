"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/**
 * Real equity only. Never fabricate a curve when history is missing.
 */
export function EquityChart({
  data,
  emptyLabel = "No equity history yet",
  color = "var(--accent)",
}: {
  data?: { t: string; equity: number }[];
  emptyLabel?: string;
  color?: string;
}) {
  if (!data || data.length === 0) {
    return (
      <div
        className="flex h-64 flex-col items-center justify-center gap-2 text-center"
        role="img"
        aria-label={emptyLabel}
      >
        <p className="qf-heading text-[var(--fg)]">{emptyLabel}</p>
        <p className="qf-caption max-w-xs">
          Connect a live session. Equity appears when the book records history.
        </p>
      </div>
    );
  }

  return (
    <div className="h-64 w-full" role="img" aria-label="Equity curve chart">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="t"
            stroke="var(--fg-subtle)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            stroke="var(--fg-subtle)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            width={56}
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
            className="tabular"
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 6,
            }}
            labelStyle={{ color: "var(--fg-muted)" }}
          />
          <Area
            type="monotone"
            dataKey="equity"
            stroke={color}
            fill="var(--accent-soft)"
            strokeWidth={1.75}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
