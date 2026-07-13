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

const demo = [
  { t: "Mon", equity: 100000 },
  { t: "Tue", equity: 100840 },
  { t: "Wed", equity: 99820 },
  { t: "Thu", equity: 101420 },
  { t: "Fri", equity: 102910 },
  { t: "Sat", equity: 103350 },
  { t: "Sun", equity: 104180 },
];

export function EquityChart({
  data,
  emptyLabel = "No equity history yet",
  color = "#2dd4bf",
}: {
  data?: { t: string; equity: number }[];
  emptyLabel?: string;
  color?: string;
}) {
  if (data && data.length === 0) {
    return (
      <div
        className="flex h-64 items-center justify-center text-sm text-[var(--fg-subtle)]"
        role="img"
        aria-label={emptyLabel}
      >
        {emptyLabel}
      </div>
    );
  }

  const series = data && data.length > 0 ? data : demo;
  const isDemo = !data;

  return (
    <div className="h-64 w-full" role="img" aria-label="Equity curve chart">
      {isDemo ? (
        <p className="mb-2 text-[10px] uppercase tracking-wider text-[var(--fg-subtle)]">
          Illustrative curve — live data replaces this when available
        </p>
      ) : null}
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.4} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="t" stroke="var(--fg-subtle)" fontSize={11} tickLine={false} axisLine={false} />
          <YAxis
            stroke="var(--fg-subtle)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            width={56}
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 10,
              boxShadow: "var(--shadow-card)",
            }}
            labelStyle={{ color: "var(--fg-muted)" }}
          />
          <Area
            type="monotone"
            dataKey="equity"
            stroke={color}
            fill="url(#equityFill)"
            strokeWidth={2.25}
            animationDuration={900}
            animationEasing="ease-out"
            isAnimationActive
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
