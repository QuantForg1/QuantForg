"use client";

import { memo } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Sparkline } from "@/components/charts/sparkline";
import { cn } from "@/lib/utils";

export const KpiMetricCard = memo(function KpiMetricCard({
  label,
  value,
  hint,
  tone = "neutral",
  trend,
  spark,
  status,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "up" | "down";
  trend?: string;
  spark?: number[];
  status?: "live" | "sync" | "offline" | "ok" | "warn";
}) {
  const statusTone =
    status === "live" || status === "ok"
      ? "success"
      : status === "warn" || status === "offline"
        ? "warning"
        : "accent";

  return (
    <Card className="qf-card-interactive overflow-hidden">
      <CardHeader className="flex-row items-start justify-between gap-2 pb-1">
        <CardTitle className="text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
          {label}
        </CardTitle>
        {status ? (
          <Badge tone={statusTone} className="gap-1">
            <span className="qf-status-dot h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
            {status}
          </Badge>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-2">
        <motion.p
          key={value}
          initial={{ opacity: 0.35, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28 }}
          className={cn(
            "tabular text-xl font-semibold tracking-tight text-[var(--fg)] sm:text-2xl",
            tone === "up" && "text-[var(--success)]",
            tone === "down" && "text-[var(--danger)]",
          )}
        >
          {value}
        </motion.p>
        <div className="flex items-end justify-between gap-2">
          <div className="min-w-0">
            {trend ? (
              <p
                className={cn(
                  "text-xs tabular",
                  tone === "up" && "text-[var(--success)]",
                  tone === "down" && "text-[var(--danger)]",
                  tone === "neutral" && "text-[var(--fg-subtle)]",
                )}
              >
                {trend}
              </p>
            ) : null}
            {hint ? <p className="truncate text-[11px] text-[var(--fg-subtle)]">{hint}</p> : null}
          </div>
          {spark && spark.length > 0 ? (
            <div className="w-20 shrink-0 sm:w-24" aria-hidden>
              <Sparkline values={spark} tone={tone} />
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
});
