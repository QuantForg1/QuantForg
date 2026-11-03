"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Layers,
  Shield,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { asRecord, num } from "@/lib/desk";
import { policyStatusText } from "@/lib/trading/admin-policy";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type PolicyPayload = {
  version?: number;
  status?: string;
  applied_version?: number | null;
  worker_confirmed?: boolean;
  source?: string;
  document?: Record<string, unknown> | null;
  enforced_min_reward_risk?: string;
  commission?: Record<string, string> | null;
};

type Overview = {
  policy?: PolicyPayload;
};

const METER_FIELDS: Array<{
  key: string;
  label: string;
  max?: number;
  suffix?: string;
}> = [
  { key: "max_planned_risk_pct", label: "Planned Risk", max: 100, suffix: "%" },
  { key: "max_aggregate_open_risk_pct", label: "Aggregate Open Risk", max: 100, suffix: "%" },
  { key: "min_reward_risk", label: "Minimum Net Reward/Risk", max: 5 },
  { key: "min_trade_quality", label: "Trade Quality", max: 100 },
  { key: "max_lot", label: "Maximum Lot", max: 1 },
  { key: "max_spread", label: "Maximum Spread", max: 5 },
  { key: "stop_atr_multiplier", label: "ATR Stop Multiplier", max: 5 },
  { key: "max_concurrent_positions", label: "Maximum Concurrent Positions", max: 20 },
  { key: "daily_loss_pct", label: "Daily Loss Limit", max: 100, suffix: "%" },
];

function shown(value: unknown): string {
  if (value == null || value === "") return "—";
  return String(value);
}

function meterPct(raw: unknown, max: number): number | null {
  const n = num(raw);
  if (!Number.isFinite(n) || max <= 0) return null;
  return Math.max(0, Math.min(100, (n / max) * 100));
}

function PolicyMeter({
  label,
  value,
  max = 100,
  suffix = "",
}: {
  label: string;
  value: unknown;
  max?: number;
  suffix?: string;
}) {
  const pct = meterPct(value, max);
  const display = value == null || value === "" ? "—" : `${shown(value)}${suffix}`;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-[var(--fg)]">{label}</p>
        <p className="text-sm font-semibold tabular text-[var(--fg)]">{display}</p>
      </div>
      <div className="relative h-2 rounded-full bg-[var(--bg)]/70" aria-hidden>
        <div
          className={cn(
            "absolute inset-y-0 left-0 rounded-full transition-[width] duration-[var(--duration-os)]",
            pct == null ? "bg-[var(--border)]" : "bg-[var(--hot)]",
          )}
          style={{ width: pct == null ? "0%" : `${pct}%` }}
        />
        {pct != null ? (
          <span
            className="absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full border-2 border-white bg-[var(--hot)] shadow-[0_0_0_3px_rgba(255,90,36,0.25)]"
            style={{ left: `calc(${pct}% - 0.5rem)` }}
          />
        ) : null}
      </div>
    </div>
  );
}

/** Read-only view of the saved owner policy. Editing stays on Admin control. */
export function OwnerPolicySummary() {
  const q = useQuery({
    queryKey: ["owner-policy-overview"],
    queryFn: () => apiFetch<Overview>("/admin/control/overview"),
    retry: false,
    staleTime: 20_000,
  });

  if (q.isLoading) {
    return (
      <Card aria-busy="true">
        <CardHeader>
          <CardTitle>Risk Settings</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-[var(--fg-muted)]">Loading saved policy…</CardContent>
      </Card>
    );
  }

  if (q.isError || !q.data?.policy) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Risk Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-[var(--fg-muted)]">
          <p>Saved policy is unavailable for this session. No settings are shown in its place.</p>
          <p>The risk check on this page still uses the live account session.</p>
        </CardContent>
      </Card>
    );
  }

  const policy = q.data.policy;
  const doc = policy.document || {};
  const confirmed =
    policy.worker_confirmed === true &&
    policy.applied_version === policy.version &&
    (policy.version ?? 0) > 0;
  const reward =
    policy.enforced_min_reward_risk && String(policy.enforced_min_reward_risk).length > 0
      ? policy.enforced_min_reward_risk
      : shown(doc.min_reward_risk);
  const storedReward = doc.min_reward_risk;
  const rewardNote =
    storedReward != null &&
    storedReward !== "" &&
    policy.enforced_min_reward_risk &&
    String(storedReward) !== String(policy.enforced_min_reward_risk)
      ? `Stored ${String(storedReward)} is not the live floor.`
      : null;
  const commission = asRecord(policy.commission);
  const allowlist = doc.gold_only === true ? "XAUUSD" : shown(doc.symbol_allowlist ?? doc.symbols);
  const planned = doc.max_planned_risk_pct;
  const aggregate = doc.max_aggregate_open_risk_pct;
  const quality = doc.min_trade_quality;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="border-[color-mix(in_srgb,var(--success)_35%,var(--border))]">
          <CardContent className="flex items-start gap-3 pt-[var(--space-4)]">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--success-soft)] text-[var(--success)]">
              <ShieldCheck className="h-5 w-5" aria-hidden />
            </span>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Risk Status
              </p>
              <p className="mt-1 text-sm font-semibold text-[var(--fg)]">
                {confirmed ? "Normal — saved policy loaded" : "Awaiting confirmation"}
              </p>
              <p className="mt-1 text-xs text-[var(--fg-muted)]">{policyStatusText(policy)}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-start gap-3 pt-[var(--space-4)]">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--hot-soft)] text-[var(--hot)]">
              <SlidersHorizontal className="h-5 w-5" aria-hidden />
            </span>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Planned Risk
              </p>
              <p className="mt-1 text-2xl font-semibold tabular">{shown(planned)}%</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-start gap-3 pt-[var(--space-4)]">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
              <Layers className="h-5 w-5" aria-hidden />
            </span>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Aggregate Open Risk
              </p>
              <p className="mt-1 text-2xl font-semibold tabular">{shown(aggregate)}%</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-start gap-3 pt-[var(--space-4)]">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--info-soft)] text-[var(--info)]">
              <Shield className="h-5 w-5" aria-hidden />
            </span>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Trade Quality
              </p>
              <p className="mt-1 text-2xl font-semibold tabular">{shown(quality)}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.4fr_0.85fr]">
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-3">
            <div>
              <CardTitle>Risk Settings</CardTitle>
              <p className="text-xs text-[var(--fg-muted)]">
                Read-only meters of the saved owner policy. Editing stays on Admin control.
              </p>
            </div>
            <Badge tone={confirmed ? "success" : "warning"}>
              {confirmed ? "Worker confirmed" : "Not confirmed loaded"}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-5">
            {METER_FIELDS.map((field) => {
              const value =
                field.key === "min_reward_risk" ? reward : doc[field.key];
              return (
                <PolicyMeter
                  key={field.key}
                  label={field.label}
                  value={value}
                  max={field.max}
                  suffix={field.suffix}
                />
              );
            })}
            {rewardNote ? <p className="text-xs text-[var(--warning)]">{rewardNote}</p> : null}
            <div className="rounded-xl border border-[var(--border)] bg-[var(--bg)]/40 px-3 py-3">
              <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Symbol Allowlist
              </p>
              <p className="mt-2 inline-flex rounded-full border border-[var(--border-strong)] bg-[var(--surface-2)] px-3 py-1 text-sm font-medium">
                {allowlist}
              </p>
            </div>
            <Button variant="secondary" size="sm" asChild>
              <Link href="/admin/control">Open policy editor</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Risk Overview</CardTitle>
            <p className="text-xs text-[var(--fg-muted)]">Saved values for quick scanning.</p>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3">
              {METER_FIELDS.map((field) => {
                const value =
                  field.key === "min_reward_risk" ? reward : doc[field.key];
                return (
                  <div
                    key={field.key}
                    className="flex items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg)]/35 px-3 py-2.5"
                  >
                    <dt className="text-sm text-[var(--fg-muted)]">{field.label}</dt>
                    <dd className="text-sm font-semibold tabular text-[var(--fg)]">
                      {value == null || value === ""
                        ? "—"
                        : `${shown(value)}${field.suffix ?? ""}`}
                    </dd>
                  </div>
                );
              })}
              <div className="flex items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg)]/35 px-3 py-2.5">
                <dt className="text-sm text-[var(--fg-muted)]">XAUUSD commission</dt>
                <dd className="text-sm font-semibold tabular text-[var(--fg)]">
                  {shown(commission.amount_usd)}{" "}
                  {shown(commission.currency) === "—" ? "" : shown(commission.currency)}
                </dd>
              </div>
            </dl>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
