"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { asRecord } from "@/lib/desk";
import { policyStatusText } from "@/lib/trading/admin-policy";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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

const FIELDS: Array<{ key: string; label: string }> = [
  { key: "max_planned_risk_pct", label: "Planned risk" },
  { key: "max_aggregate_open_risk_pct", label: "Aggregate open risk" },
  { key: "min_trade_quality", label: "Trade quality" },
  { key: "max_lot", label: "Maximum lot" },
  { key: "max_spread", label: "Maximum spread" },
  { key: "daily_loss_pct", label: "Daily loss halt" },
  { key: "max_concurrent_positions", label: "Maximum concurrent positions" },
  { key: "stop_atr_multiplier", label: "ATR stop multiplier" },
];

function shown(value: unknown): string {
  if (value == null || value === "") return "—";
  return String(value);
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
          <CardTitle>Saved owner policy</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-[var(--fg-muted)]">Loading saved policy…</CardContent>
      </Card>
    );
  }

  if (q.isError || !q.data?.policy) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Saved owner policy</CardTitle>
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

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3">
        <div>
          <CardTitle>Saved owner policy</CardTitle>
          <p className="text-xs text-[var(--fg-muted)]">{policyStatusText(policy)}</p>
        </div>
        <Badge tone={confirmed ? "success" : "warning"}>
          {confirmed ? "Worker confirmed" : "Not confirmed loaded"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {FIELDS.map((field) => (
            <div key={field.key} className="rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-2">
              <dt className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">{field.label}</dt>
              <dd className="mt-1 text-sm font-semibold tabular text-[var(--fg)]">{shown(doc[field.key])}</dd>
            </div>
          ))}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-2">
            <dt className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">Minimum net reward/risk</dt>
            <dd className="mt-1 text-sm font-semibold tabular text-[var(--fg)]">{reward}</dd>
            {rewardNote ? <p className="mt-1 text-xs text-[var(--warning)]">{rewardNote}</p> : null}
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-2">
            <dt className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">Symbol allowlist</dt>
            <dd className="mt-1 text-sm font-semibold text-[var(--fg)]">{allowlist}</dd>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-2">
            <dt className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">XAUUSD commission</dt>
            <dd className="mt-1 text-sm font-semibold tabular text-[var(--fg)]">
              {shown(commission.amount_usd)} {shown(commission.currency) === "—" ? "" : shown(commission.currency)}
            </dd>
          </div>
        </dl>
        <Button variant="secondary" size="sm" asChild>
          <Link href="/admin/control">Open policy editor</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
