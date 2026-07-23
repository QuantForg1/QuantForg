"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/**
 * Read-only trend line for Opportunity Timeline.
 * Never fabricates points — empty when series missing.
 */
export function OpportunityTrendChart({
  data,
  title,
  color = "var(--accent)",
  yDomain,
  emptyLabel = "No evaluations yet",
}: {
  data?: { label: string; v: number; t?: string }[];
  title: string;
  color?: string;
  yDomain?: [number, number] | ["auto", "auto"];
  emptyLabel?: string;
}) {
  if (!data || data.length === 0) {
    return (
      <div
        className="flex h-44 flex-col items-center justify-center gap-1 border border-[var(--border)] bg-[var(--bg)]/30"
        role="img"
        aria-label={emptyLabel}
      >
        <p className="text-[12px] font-semibold text-[var(--fg)]">{title}</p>
        <p className="text-[11px] text-[var(--fg-subtle)]">{emptyLabel}</p>
      </div>
    );
  }

  return (
    <div className="border border-[var(--border)] bg-[var(--surface)]/80 px-2 pb-2 pt-3">
      <p className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {title}
      </p>
      <div className="h-40 w-full" role="img" aria-label={title}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid
              stroke="var(--border)"
              strokeDasharray="3 3"
              vertical={false}
            />
            <XAxis
              dataKey="label"
              stroke="var(--fg-subtle)"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
              minTickGap={24}
            />
            <YAxis
              stroke="var(--fg-subtle)"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              width={36}
              domain={yDomain ?? ["auto", "auto"]}
              className="tabular-nums"
            />
            <Tooltip
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                fontSize: 11,
              }}
              labelStyle={{ color: "var(--fg-muted)" }}
            />
            <Line
              type="monotone"
              dataKey="v"
              stroke={color}
              strokeWidth={1.75}
              dot={data.length <= 24}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
