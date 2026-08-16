"use client";

import { memo, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function NocPanel({
  title,
  children,
  className,
  action,
  id,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
  id?: string;
}) {
  return (
    <section
      id={id}
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

export type HealthDisplay =
  | "Healthy"
  | "Warning"
  | "Disconnected"
  | "Disabled"
  | "Unknown";

export function normalizeHealthStatus(
  status: string,
  detail?: unknown,
): HealthDisplay {
  const s = String(status || "").toLowerCase();
  const d = String(detail ?? "").toLowerCase();
  if (d.includes("disabled") || s === "disabled") return "Disabled";
  if (
    s === "disconnected" ||
    d.includes("disconnected") ||
    s === "critical" ||
    s === "unhealthy" ||
    s === "down"
  ) {
    if (d.includes("disabled")) return "Disabled";
    return s === "critical" || s === "unhealthy" || s === "down" || s === "disconnected"
      ? "Disconnected"
      : "Disconnected";
  }
  if (s === "healthy" || s === "ok" || s === "pass" || s === "connected" || s === "up") {
    return "Healthy";
  }
  if (s === "warning" || s === "degraded" || s === "unknown") return "Warning";
  return "Unknown";
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
  const display = normalizeHealthStatus(status, detail);
  const ok = display === "Healthy";
  const warn = display === "Warning" || display === "Unknown";
  const disabled = display === "Disabled";
  return (
    <div
      className={cn(
        "relative overflow-hidden border px-3 py-3 transition-colors duration-[var(--duration-os)]",
        ok && "border-[var(--success)]/70 bg-[var(--success-soft)]",
        warn && !ok && "border-[var(--warning)]/70 bg-[var(--warning-soft)]",
        !ok && !warn && !disabled && "border-[var(--danger)]/70 bg-[var(--danger-soft)]",
        disabled && "border-[var(--border)] bg-[var(--surface-2)]",
      )}
    >
      <div
        className={cn(
          "absolute right-2 top-2 h-2 w-2 rounded-full",
          ok && "bg-[var(--success)] shadow-[0_0_8px_var(--accent)]",
          warn && "bg-[var(--warning)]",
          !ok && !warn && !disabled && "bg-[var(--danger)]",
          disabled && "bg-[var(--fg-subtle)]",
        )}
        aria-hidden
      />
      <div className="flex items-center justify-between gap-2 pr-4">
        <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg)]">
          {label}
        </span>
        <Badge
          tone={
            ok
              ? "success"
              : warn
                ? "warning"
                : disabled
                  ? "neutral"
                  : "danger"
          }
        >
          {display}
        </Badge>
      </div>
      <p className="mt-2 font-mono text-[11px] text-[var(--fg-muted)]">
        Latency:{" "}
        {latencyMs == null || latencyMs === "" ? "—" : `${latencyMs} ms`}
      </p>
      <p
        className="mt-0.5 truncate font-mono text-[10px] text-[var(--fg-subtle)]"
        title={String(heartbeat ?? "")}
      >
        Heartbeat:{" "}
        {heartbeat == null || heartbeat === "" ? "—" : String(heartbeat)}
      </p>
      {detail ? (
        <p
          className="mt-1 truncate text-[11px] text-[var(--fg-muted)]"
          title={String(detail)}
        >
          {String(detail)}
        </p>
      ) : null}
    </div>
  );
});

export function pipelineTone(
  status: string,
): "ok" | "warn" | "bad" | undefined {
  const u = status.toUpperCase();
  if (u === "PASS") return "ok";
  if (u === "FAIL") return "bad";
  if (u === "RUNNING" || u === "WAIT" || u === "WAITING") return "warn";
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

/** Circular gauge 0–100 — empty ring when value unavailable (never mocked). */
export const GaugeRing = memo(function GaugeRing({
  label,
  value,
  max = 100,
  threshold,
}: {
  label: string;
  value: unknown;
  max?: number;
  threshold?: number;
}) {
  const n = typeof value === "number" ? value : Number(value);
  const ready = Number.isFinite(n);
  const pct = ready ? Math.min(100, Math.max(0, (n / max) * 100)) : 0;
  const r = 36;
  const c = 2 * Math.PI * r;
  const dash = ready ? (pct / 100) * c : 0;
  const tone =
    ready && threshold != null
      ? n >= threshold
        ? "ok"
        : "bad"
      : ready
        ? "ok"
        : undefined;
  return (
    <div className="flex flex-col items-center gap-1 px-2 py-2">
      <svg width="88" height="88" viewBox="0 0 88 88" aria-hidden>
        <circle
          cx="44"
          cy="44"
          r={r}
          fill="none"
          stroke="var(--surface-2)"
          strokeWidth="8"
        />
        {ready ? (
          <circle
            cx="44"
            cy="44"
            r={r}
            fill="none"
            stroke={
              tone === "bad" ? "var(--danger)" : "var(--accent)"
            }
            strokeWidth="8"
            strokeLinecap="butt"
            strokeDasharray={`${dash} ${c - dash}`}
            transform="rotate(-90 44 44)"
            className="transition-[stroke-dasharray] duration-[var(--duration-os)]"
          />
        ) : null}
        <text
          x="44"
          y="48"
          textAnchor="middle"
          className="fill-[var(--fg)] font-mono text-[14px]"
          style={{ fontSize: 14 }}
        >
          {ready ? Math.round(n) : "—"}
        </text>
      </svg>
      <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </span>
    </div>
  );
});

/** Sparkline from real numeric series only — elegant empty when no data. */
export const SparkBars = memo(function SparkBars({
  label,
  series,
  height = 64,
}: {
  label: string;
  series: number[];
  height?: number;
}) {
  const max = useMemo(() => {
    if (!series.length) return 0;
    return Math.max(...series.map((v) => Math.abs(v)), 1e-9);
  }, [series]);
  return (
    <div className="border border-[var(--border)] bg-[var(--surface-2)] p-2">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </p>
      {series.length === 0 ? (
        <p className="py-6 text-center font-mono text-[11px] text-[var(--fg-subtle)]">
          No series in telemetry
        </p>
      ) : (
        <div
          className="flex items-end gap-px"
          style={{ height }}
          role="img"
          aria-label={label}
        >
          {series.map((v, i) => {
            const h = Math.max(2, (Math.abs(v) / max) * height);
            const neg = v < 0;
            return (
              <div
                key={i}
                className={cn(
                  "min-w-[2px] flex-1 transition-[height] duration-[var(--duration-os)]",
                  neg ? "bg-[var(--danger)]" : "bg-[var(--accent)]",
                )}
                style={{ height: h }}
                title={String(v)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
});

export const DECISION_TONES: Record<
  string,
  "ok" | "warn" | "bad" | "neutral"
> = {
  BUY: "ok",
  SELL: "ok",
  WAIT: "warn",
  WATCH: "warn",
  NO_TRADE: "warn",
  "NO TRADE": "warn",
};
