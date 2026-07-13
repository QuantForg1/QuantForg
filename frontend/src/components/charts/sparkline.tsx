"use client";

import { memo } from "react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { cn } from "@/lib/utils";

export const Sparkline = memo(function Sparkline({
  values,
  tone = "neutral",
  className,
}: {
  values: number[];
  tone?: "neutral" | "up" | "down";
  className?: string;
}) {
  if (!values.length) {
    return (
      <div
        className={cn("h-8 w-full rounded bg-[var(--surface-2)]/60", className)}
        aria-hidden
      />
    );
  }

  const data = values.map((v, i) => ({ i, v }));
  const stroke =
    tone === "up" ? "var(--success)" : tone === "down" ? "var(--danger)" : "var(--accent)";

  return (
    <div className={cn("h-8 w-full", className)} aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <Area
            type="monotone"
            dataKey="v"
            stroke={stroke}
            fill={stroke}
            fillOpacity={0.15}
            strokeWidth={1.5}
            isAnimationActive
            animationDuration={600}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
});
