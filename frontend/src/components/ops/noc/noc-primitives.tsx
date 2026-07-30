"use client";

import { memo } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function NocPanel({
  title,
  children,
  className,
  action,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
}) {
  return (
    <section
      className={cn(
        "border border-[var(--border)] bg-[var(--surface)]",
        className,
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
        {action}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

export function NocRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "ok" | "warn" | "bad";
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-[var(--border)]/60 py-1.5 last:border-0">
      <span className="text-[11px] uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
        {label}
      </span>
      <span
        className={cn(
          "max-w-[70%] truncate text-right font-mono text-[12px] text-[var(--fg)]",
          tone === "ok" && "text-[var(--success)]",
          tone === "warn" && "text-[var(--warning)]",
          tone === "bad" && "text-[var(--danger)]",
        )}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

export const HealthCard = memo(function HealthCard({
  label,
  status,
  latencyMs,
  heartbeat,
  detail,
}: {
  label: string;
  status: string;
  latencyMs?: unknown;
  heartbeat?: unknown;
  detail?: unknown;
}) {
  const s = String(status || "unknown").toLowerCase();
  const passed = s === "healthy" || s === "ok" || s === "pass";
  const warn = s === "warning" || s === "degraded" || s === "unknown";
  return (
    <div
      className={cn(
        "border px-3 py-3 transition-colors duration-[var(--duration-os)]",
        passed && "border-[var(--success)] bg-[var(--success-soft)]",
        warn && !passed && "border-[var(--warning)] bg-[var(--warning-soft)]",
        !passed && !warn && "border-[var(--danger)] bg-[var(--danger-soft)]",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg)]">
          {label}
        </span>
        <Badge tone={passed ? "success" : warn ? "warning" : "danger"}>
          {passed ? "Healthy" : warn ? "Warning" : "Critical"}
        </Badge>
      </div>
      <p className="mt-2 font-mono text-[11px] text-[var(--fg-muted)]">
        Latency: {latencyMs == null || latencyMs === "" ? "—" : `${latencyMs} ms`}
      </p>
      <p className="mt-0.5 truncate font-mono text-[10px] text-[var(--fg-subtle)]" title={String(heartbeat ?? "")}>
        Heartbeat: {heartbeat == null || heartbeat === "" ? "—" : String(heartbeat)}
      </p>
      {detail ? (
        <p className="mt-1 truncate text-[11px] text-[var(--fg-muted)]" title={String(detail)}>
          {String(detail)}
        </p>
      ) : null}
    </div>
  );
});

export function pipelineTone(status: string): "ok" | "warn" | "bad" | undefined {
  const u = status.toUpperCase();
  if (u === "PASS") return "ok";
  if (u === "FAIL") return "bad";
  if (u === "RUNNING") return "warn";
  return undefined;
}

export function fmt(v: unknown, fallback = "—"): string {
  if (v == null || v === "") return fallback;
  if (typeof v === "object") {
    try {
      return JSON.stringify(v);
    } catch {
      return fallback;
    }
  }
  return String(v);
}

/** Compact real-value bar — renders empty when metric is unavailable (never mock). */
export const MetricBar = memo(function MetricBar({
  label,
  value,
  max,
}: {
  label: string;
  value: unknown;
  max?: number;
}) {
  const n = typeof value === "number" ? value : Number(value);
  const ready = Number.isFinite(n);
  const denom = max && max > 0 ? max : Math.max(n, 1);
  const pct = ready ? Math.min(100, Math.max(0, (n / denom) * 100)) : 0;
  return (
    <div className="border-b border-[var(--border)]/60 py-1.5 last:border-0">
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-[11px] uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
          {label}
        </span>
        <span className="font-mono text-[12px] text-[var(--fg)]">
          {ready ? String(n) : "—"}
        </span>
      </div>
      <div className="h-1.5 w-full bg-[var(--surface-2)]">
        {ready ? (
          <div
            className="h-full bg-[var(--accent)] transition-[width] duration-[var(--duration-os)]"
            style={{ width: `${pct}%` }}
          />
        ) : null}
      </div>
    </div>
  );
});
