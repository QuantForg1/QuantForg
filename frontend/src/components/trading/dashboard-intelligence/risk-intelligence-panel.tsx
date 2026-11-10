"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  deriveRiskIntelligence,
  type RiskHealthState,
} from "@/lib/dashboard/risk-intelligence";
import { cn, formatCurrency, formatNumber } from "@/lib/utils";

function toneFor(state: RiskHealthState): "success" | "warning" | "danger" | "neutral" {
  if (state === "Healthy") return "success";
  if (state === "Warning") return "warning";
  if (state === "Restricted" || state === "Halted") return "danger";
  return "neutral";
}

function Row({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="flex min-w-0 items-start justify-between gap-3 border-b border-[var(--border)] py-2 last:border-b-0">
      <div className="min-w-0">
        <p className="text-xs text-[var(--fg-muted)]">{label}</p>
        {hint ? (
          <p className="mt-0.5 text-[11px] text-[var(--fg-subtle)]">{hint}</p>
        ) : null}
      </div>
      <p className="shrink-0 font-mono text-sm tabular text-[var(--fg)]">{value}</p>
    </div>
  );
}

/** Customer-facing risk meters. Never renders Owner Policy numerical configuration. */
export function RiskIntelligencePanel({
  equity,
  balance,
  floatingPnl,
  todayPnl,
  openPositionCount,
  riskLocked,
  emergencyStop,
  liveAuthorization,
  ordersMaySubmit,
  currency = "USD",
  showRiskCenterLink = true,
  dailyLossHaltPercent,
  maxAggregateOpenRiskPercent,
  maxConcurrentPositions,
  riskPerTradePercent,
}: {
  equity: unknown;
  balance: unknown;
  floatingPnl: unknown;
  todayPnl: unknown;
  openPositionCount: number;
  riskLocked?: unknown;
  emergencyStop?: unknown;
  liveAuthorization?: unknown;
  ordersMaySubmit?: unknown;
  currency?: string;
  showRiskCenterLink?: boolean;
  dailyLossHaltPercent?: number;
  maxAggregateOpenRiskPercent?: number;
  maxConcurrentPositions?: number;
  riskPerTradePercent?: number;
}) {
  const snap = deriveRiskIntelligence({
    equity,
    balance,
    floatingPnl,
    todayPnl,
    openPositionCount,
    riskLocked,
    emergencyStop,
    liveAuthorization,
    ordersMaySubmit,
    dailyLossHaltPercent,
    maxAggregateOpenRiskPercent,
    maxConcurrentPositions,
    riskPerTradePercent,
  });
  const code = currency && currency !== "—" ? currency : "USD";

  return (
    <section
      aria-labelledby="risk-intelligence"
      className="space-y-3 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-[var(--shadow-card)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2
              id="risk-intelligence"
              className="text-sm font-medium text-[var(--fg)]"
            >
              Account Risk Overview
            </h2>
            <Badge tone={toneFor(snap.state)}>{snap.state}</Badge>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-[var(--fg-muted)]">
            {snap.reason}
          </p>
        </div>
        {showRiskCenterLink ? (
          <Button variant="ghost" size="sm" asChild>
            <Link href="/risk-center">Risk Center</Link>
          </Button>
        ) : null}
      </div>

      <div className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg)]/30 px-3">
        <Row
          label="Current drawdown"
          value={
            Number.isFinite(snap.currentDrawdownPct)
              ? `${formatNumber(snap.currentDrawdownPct, 2)}%`
              : "—"
          }
        />
        <Row
          label="Daily loss usage"
          value={
            Number.isFinite(snap.dailyLossUsedPct)
              ? `${formatNumber(snap.dailyLossUsedPct, 2)}%`
              : "—"
          }
          hint="Measured against your effective daily-loss preference"
        />
        <Row
          label="Remaining daily loss allowance"
          value={
            Number.isFinite(snap.dailyLossRemainingPct)
              ? `${formatNumber(snap.dailyLossRemainingPct, 2)}%`
              : "—"
          }
        />
        <Row
          label="Aggregate open risk"
          value={
            Number.isFinite(snap.aggregateOpenRiskPct)
              ? `${formatNumber(snap.aggregateOpenRiskPct, 2)}%`
              : "—"
          }
          hint="Against your effective open-risk preference"
        />
        <Row
          label="Open positions"
          value={`${snap.openPositionCount} / ${snap.maxConcurrentPositions}`}
          hint="Versus your personal concurrent-position preference"
        />
        <Row
          label="Floating P&L"
          value={
            Number.isFinite(snap.floatingPnl)
              ? formatCurrency(snap.floatingPnl, code)
              : "—"
          }
        />
      </div>

      <p
        className={cn(
          "rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 text-xs text-[var(--fg-muted)]",
          snap.state === "Healthy" &&
            "bg-[color-mix(in_srgb,var(--success-soft)_35%,var(--bg))]",
          snap.state === "Warning" &&
            "bg-[color-mix(in_srgb,var(--warning-soft)_40%,var(--bg))]",
          (snap.state === "Restricted" || snap.state === "Halted") &&
            "bg-[color-mix(in_srgb,var(--danger-soft)_35%,var(--bg))]",
        )}
      >
        Meters reflect your account session and effective preferences. Live
        enforcement remains in the existing risk engine and OMS path.
      </p>
    </section>
  );
}
