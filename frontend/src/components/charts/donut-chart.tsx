"use client";

import { memo } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { cn } from "@/lib/utils";

/* RC4 palette: accent → status → muted (no RC3 teal). */
const COLORS = ["#00d4e0", "#2f9e7a", "#d4a017", "#e05d5d", "#0891a8", "#9aa8bc", "#6b7a8f"];

export const DonutChart = memo(function DonutChart({
  data,
  className,
}: {
  data: { name: string; value: number }[];
  className?: string;
}) {
  if (!data.length) {
    return (
      <div
        className={cn(
          "flex h-56 items-center justify-center text-sm text-[var(--fg-subtle)]",
          className,
        )}
      >
        No allocation data yet
      </div>
    );
  }

  const total = data.reduce((s, d) => s + d.value, 0) || 1;

  return (
    <div className={cn("grid gap-4 sm:grid-cols-[1fr_0.9fr]", className)}>
      <div className="h-56" role="img" aria-label="Asset allocation chart">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius="58%"
              outerRadius="82%"
              paddingAngle={2}
              stroke="transparent"
              isAnimationActive
              animationDuration={800}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 10,
              }}
              formatter={(value: number, name: string) => [
                `${((value / total) * 100).toFixed(1)}%`,
                name,
              ]}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="space-y-2 self-center">
        {data.map((d, i) => (
          <li key={d.name} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex items-center gap-2 text-[var(--fg-muted)]">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: COLORS[i % COLORS.length] }}
                aria-hidden
              />
              {d.name}
            </span>
            <span className="tabular text-[var(--fg)]">
              {((d.value / total) * 100).toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
});
