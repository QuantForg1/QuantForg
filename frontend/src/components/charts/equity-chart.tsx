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

export function EquityChart({ data = demo }: { data?: { t: string; equity: number }[] }) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2dd4bf" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#2dd4bf" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="t" stroke="var(--fg-subtle)" fontSize={12} tickLine={false} />
          <YAxis
            stroke="var(--fg-subtle)"
            fontSize={12}
            tickLine={false}
            width={64}
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
            }}
          />
          <Area
            type="monotone"
            dataKey="equity"
            stroke="#2dd4bf"
            fill="url(#equityFill)"
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
