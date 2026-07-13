"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export function DeskBarChart({
  data,
  dataKey = "value",
  nameKey = "label",
}: {
  data: Record<string, string | number>[];
  dataKey?: string;
  nameKey?: string;
}) {
  if (!data.length) {
    return (
      <div
        className="flex h-64 items-center justify-center text-sm text-[var(--fg-subtle)]"
        role="img"
        aria-label="No series data yet"
      >
        No series data yet
      </div>
    );
  }

  return (
    <div className="h-64 w-full" role="img" aria-label="Bar chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey={nameKey}
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
            width={44}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 10,
              boxShadow: "var(--shadow-card)",
            }}
          />
          <Bar dataKey={dataKey} radius={[5, 5, 0, 0]} animationDuration={800} isAnimationActive>
            {data.map((entry, i) => {
              const v = Number(entry[dataKey] ?? 0);
              return (
                <Cell
                  key={i}
                  fill={v >= 0 ? "var(--success)" : "var(--danger)"}
                  fillOpacity={0.88}
                />
              );
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
