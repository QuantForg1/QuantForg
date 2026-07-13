"use client";

import { memo, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export const StatCard = memo(function StatCard({
  label,
  value,
  hint,
  tone = "neutral",
  className,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "up" | "down";
  className?: string;
}) {
  const [display, setDisplay] = useState(value);

  useEffect(() => {
    setDisplay(value);
  }, [value]);

  return (
    <Card className={cn("qf-card-interactive", className)}>
      <CardHeader className="pb-1">
        <CardTitle className="text-xs font-medium uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <motion.p
          key={display}
          initial={{ opacity: 0.4, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className={cn(
            "tabular text-2xl font-semibold tracking-tight text-[var(--fg)]",
            tone === "up" && "text-[var(--success)]",
            tone === "down" && "text-[var(--danger)]",
          )}
        >
          {display}
        </motion.p>
        {hint ? <p className="mt-1.5 text-xs text-[var(--fg-subtle)]">{hint}</p> : null}
      </CardContent>
    </Card>
  );
});
