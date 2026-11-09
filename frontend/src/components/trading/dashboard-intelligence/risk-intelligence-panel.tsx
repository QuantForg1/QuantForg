"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  deriveRiskIntelligence,
  type RiskHealthState,
} from "@/lib/dashboard/risk-intelligence";
import { OWNER_RISK_POLICY_DISPLAY } from "@/lib/trading/owner-risk-policy-display";
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
  });
  const code = currency && currency !== "—" ? currency : "USD";
  const policy = OWNER_RISK_POLICY_DISPLAY;

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
              Risk Intelligence
            </h2>
            <Badge tone={toneFor(snap.state)}>{snap.state}</Badge>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-[var(--fg-muted)]">
            {snap.reason}
          </p>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/risk-center">Risk Center</Link>
        </Button>
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
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
            hint={`Halt ceiling ${policy.dailyLossHaltPercent}%`}
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
            hint={`Ceiling ${policy.maxAggregateOpenRiskPercent}%`}
          />
          <Row
            label="Open-position exposure"
            value={`${snap.openPositionCount} / ${snap.maxConcurrentPositions}`}
            hint={`Max concurrent ${policy.maxConcurrentPositions}`}
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

        <div
          className={cn(
            "rounded-[var(--radius-os)] border px-3 py-3 text-xs leading-relaxed text-[var(--fg-muted)]",
            snap.state === "Healthy" &&
              "border-[var(--border)] bg-[color-mix(in_srgb,var(--success-soft)_40%,var(--bg))]",
            snap.state === "Warning" &&
              "border-[var(--border)] bg-[color-mix(in_srgb,var(--warning-soft)_45%,var(--bg))]",
            (snap.state === "Restricted" || snap.state === "Halted") &&
              "border-[var(--border)] bg-[color-mix(in_srgb,var(--danger-soft)_40%,var(--bg))]",
          )}
        >
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Owner policy (read-only)
          </p>
          <ul className="mt-2 space-y-1.5">
            <li>Max lot {policy.maxLot}</li>
            <li>Risk / trade {policy.riskPerTradePercent}%</li>
            <li>Daily loss halt {policy.dailyLossHaltPercent}%</li>
            <li>Aggregate open risk {policy.maxAggregateOpenRiskPercent}%</li>
            <li>Min trade quality {policy.minimumTradeQuality}</li>
            <li>Mandatory stop-loss · no grid / martingale / averaging</li>
          </ul>
          <p className="mt-3 text-[11px] text-[var(--fg-subtle)]">
            This panel does not submit trades or change LIVE ceilings. Enforcement
            remains in the existing risk engine.
          </p>
        </div>
      </div>
    </section>
  );
}
