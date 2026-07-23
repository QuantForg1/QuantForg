"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

/** Premium steel panel — Design Bible compliant (no neon). */
export function OpsPanel({
  title,
  children,
  action,
  className,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "border border-[var(--border)] bg-[var(--surface)]/90 backdrop-blur-[2px] transition-opacity duration-[var(--duration-os)]",
        className,
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2.5">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--fg-subtle)]">
          {title}
        </h2>
        {action}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

export function MetricCard({
  label,
  value,
  tone,
  large,
}: {
  label: string;
  value: string;
  tone?: "ok" | "warn" | "bad" | "buy" | "sell" | "accent" | "neutral";
  large?: boolean;
}) {
  const color =
    tone === "ok" || tone === "buy"
      ? "text-[var(--success)]"
      : tone === "warn"
        ? "text-[var(--warning)]"
        : tone === "bad" || tone === "sell"
          ? "text-[var(--danger)]"
          : tone === "accent"
            ? "text-[var(--accent)]"
            : "text-[var(--fg)]";
  return (
    <div
      className={cn(
        "min-w-0 border border-[var(--border)] bg-[var(--bg)]/40 px-3 py-3 transition-[border-color,background-color] duration-[var(--duration-os)]",
        large && "py-4",
      )}
    >
      <p className="text-[9px] font-medium uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p
        className={cn(
          "mt-1.5 truncate font-mono tabular tracking-tight",
          large ? "text-[22px] leading-none" : "text-[15px] leading-tight",
          color,
        )}
        title={value}
      >
        {value}
      </p>
    </div>
  );
}

export function StatusPill({
  label,
  ok,
  warn,
}: {
  label: string;
  ok?: boolean;
  warn?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border px-2 py-1 text-[10px] font-medium uppercase tracking-[0.1em]",
        ok
          ? "border-[var(--success)]/40 bg-[var(--success-soft)] text-[var(--success)]"
          : warn
            ? "border-[var(--warning)]/40 bg-[var(--warning-soft)] text-[var(--warning)]"
            : "border-[var(--danger)]/40 bg-[var(--danger-soft)] text-[var(--danger)]",
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          ok
            ? "bg-[var(--success)]"
            : warn
              ? "bg-[var(--warning)]"
              : "bg-[var(--danger)]",
        )}
        aria-hidden
      />
      {label}
    </span>
  );
}

export function UtcClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return (
    <span className="font-mono text-[11px] tabular text-[var(--fg-muted)]">
      {now.toISOString().replace("T", " ").slice(0, 19)} UTC
    </span>
  );
}

export type PipelineStageState = "waiting" | "running" | "success" | "failed";

export function ExecutionPipeline({
  stages,
}: {
  stages: { id: string; label: string; state: PipelineStageState; detail?: string }[];
}) {
  return (
    <div className="overflow-x-auto pb-1">
      <ol className="flex min-w-max items-stretch gap-0">
        {stages.map((s, i) => (
          <li key={s.id} className="flex items-center">
            <div
              className={cn(
                "w-[7.25rem] border px-2.5 py-2.5 transition-colors duration-[var(--duration-os)]",
                s.state === "waiting" &&
                  "border-[var(--border)] bg-[var(--surface-2)] text-[var(--fg-subtle)]",
                s.state === "running" &&
                  "border-[var(--accent)]/50 bg-[var(--accent-soft)] text-[var(--accent)]",
                s.state === "success" &&
                  "border-[var(--success)]/45 bg-[var(--success-soft)] text-[var(--success)]",
                s.state === "failed" &&
                  "border-[var(--danger)]/45 bg-[var(--danger-soft)] text-[var(--danger)]",
              )}
            >
              <p className="text-[9px] font-semibold uppercase tracking-[0.12em]">
                {s.label}
              </p>
              <p className="mt-1 font-mono text-[10px] tabular opacity-90">
                {s.state === "waiting"
                  ? "WAITING"
                  : s.state === "running"
                    ? "RUNNING"
                    : s.state === "success"
                      ? "OK"
                      : "FAIL"}
              </p>
              {s.detail ? (
                <p className="mt-1 truncate text-[9px] text-[var(--fg-muted)]" title={s.detail}>
                  {s.detail}
                </p>
              ) : null}
            </div>
            {i < stages.length - 1 ? (
              <span
                className="px-1 font-mono text-[10px] text-[var(--fg-subtle)]"
                aria-hidden
              >
                →
              </span>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}

export function BiasMeter({ bias }: { bias: "BUY" | "SELL" | "WAIT" }) {
  return (
    <div className="grid grid-cols-3 gap-1">
      {(["BUY", "SELL", "WAIT"] as const).map((b) => (
        <div
          key={b}
          className={cn(
            "border px-2 py-3 text-center font-mono text-[13px] font-semibold tracking-[0.08em] transition-colors duration-[var(--duration-os)]",
            bias === b && b === "BUY" && "border-[var(--success)] bg-[var(--success-soft)] text-[var(--success)]",
            bias === b && b === "SELL" && "border-[var(--danger)] bg-[var(--danger-soft)] text-[var(--danger)]",
            bias === b && b === "WAIT" && "border-[var(--accent)]/50 bg-[var(--accent-soft)] text-[var(--accent)]",
            bias !== b && "border-[var(--border)] text-[var(--fg-subtle)] opacity-50",
          )}
        >
          {b}
        </div>
      ))}
    </div>
  );
}

export function HealthDot({
  label,
  ok,
  value,
}: {
  label: string;
  ok: boolean | null;
  value?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-2 border border-[var(--border)] bg-[var(--bg)]/35 px-2.5 py-2">
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "h-2 w-2 rounded-full",
            ok === true && "bg-[var(--success)]",
            ok === false && "bg-[var(--danger)]",
            ok === null && "bg-[var(--fg-subtle)]",
          )}
          aria-hidden
        />
        <span className="text-[11px] uppercase tracking-[0.08em] text-[var(--fg-muted)]">
          {label}
        </span>
      </div>
      <Badge tone={ok === true ? "success" : ok === false ? "danger" : "neutral"}>
        {value ?? (ok === true ? "OK" : ok === false ? "DOWN" : "—")}
      </Badge>
    </div>
  );
}

export function JournalRow({
  time,
  type,
  reason,
  status,
  latency,
}: {
  time: string;
  type: string;
  reason: string;
  status: string;
  latency: string;
}) {
  const bad =
    /fail|reject|block|error|denied/i.test(status) ||
    /fail|reject|block/i.test(type);
  const ok = /success|fill|ok|pass|forward/i.test(status);
  return (
    <li className="grid grid-cols-[4.75rem_6.5rem_1fr_5.5rem_4.5rem] items-start gap-2 border-b border-[var(--border)]/50 py-2 text-[11px] last:border-0 max-md:grid-cols-[4rem_1fr]">
      <span className="font-mono tabular text-[var(--fg-subtle)]">{time}</span>
      <span className="font-medium uppercase tracking-[0.06em] text-[var(--fg)]">
        {type}
      </span>
      <span className="truncate text-[var(--fg-muted)]" title={reason}>
        {reason || "—"}
      </span>
      <span
        className={cn(
          "font-mono uppercase",
          bad && "text-[var(--danger)]",
          ok && "text-[var(--success)]",
          !bad && !ok && "text-[var(--fg-muted)]",
        )}
      >
        {status}
      </span>
      <span className="font-mono tabular text-right text-[var(--fg-subtle)]">
        {latency}
      </span>
    </li>
  );
}
