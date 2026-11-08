"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { CreditCard } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  DeskEmpty,
  DeskError,
  DeskSkeleton,
  DeskTable,
} from "@/components/desk/primitives";
import { ConfirmDialog } from "@/components/execution/confirm-dialog";
import { billingApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";
import {
  canAccessIteOps,
  iteOpsAccessDeniedMessage,
} from "@/lib/auth/ite-ops-access";

const ADMIN_PLANS_KEY = ["admin-billing-plans"];
const ADMIN_REVENUE_KEY = ["admin-billing-revenue"];

type PlanDraft = {
  active: boolean;
  monthly_price_usd: string;
  annual_price_usd: string;
  billing_interval: string;
  grace_period_days: string;
};

function fmtUsd(v: unknown): string {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

function planId(row: Record<string, unknown>): string {
  return str(row.id ?? row.plan_id, "");
}

function draftFromPlan(row: Record<string, unknown>): PlanDraft {
  return {
    active: row.active !== false,
    monthly_price_usd:
      row.monthly_price_usd != null ? String(row.monthly_price_usd) : "",
    annual_price_usd:
      row.annual_price_usd != null ? String(row.annual_price_usd) : "",
    billing_interval: str(row.billing_interval, "monthly"),
    grace_period_days:
      row.grace_period_days != null ? String(row.grace_period_days) : "",
  };
}

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-medium uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="font-mono text-2xl font-semibold text-[var(--fg)]">{value}</p>
      </CardContent>
    </Card>
  );
}

function PlanRowEditor({
  row,
  saving,
  onSave,
}: {
  row: Record<string, unknown>;
  saving: boolean;
  onSave: (planId: string, body: Record<string, unknown>) => void;
}) {
  const pid = planId(row);
  const [draft, setDraft] = useState<PlanDraft>(() => draftFromPlan(row));

  useEffect(() => {
    setDraft(draftFromPlan(row));
  }, [row]);

  return (
    <tr className="border-b border-[var(--border)]">
      <td className="px-3 py-2 align-middle">
        <div className="font-medium text-[var(--fg)]">{str(row.name, pid)}</div>
        <div className="font-mono text-[11px] text-[var(--fg-muted)]">{pid}</div>
      </td>
      <td className="px-3 py-2 align-middle">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-[var(--border)]"
            checked={draft.active}
            onChange={(e) =>
              setDraft((d) => ({ ...d, active: e.target.checked }))
            }
            aria-label={`${pid} active`}
          />
          {draft.active ? (
            <Badge tone="success">Active</Badge>
          ) : (
            <Badge tone="neutral">Inactive</Badge>
          )}
        </label>
      </td>
      <td className="px-3 py-2 align-middle">
        <Input
          type="number"
          min={0}
          step="0.01"
          value={draft.monthly_price_usd}
          onChange={(e) =>
            setDraft((d) => ({ ...d, monthly_price_usd: e.target.value }))
          }
          className="h-8 max-w-[7rem] font-mono text-sm"
          aria-label={`${pid} monthly USD`}
        />
      </td>
      <td className="px-3 py-2 align-middle">
        <Input
          type="number"
          min={0}
          step="0.01"
          value={draft.annual_price_usd}
          onChange={(e) =>
            setDraft((d) => ({ ...d, annual_price_usd: e.target.value }))
          }
          className="h-8 max-w-[7rem] font-mono text-sm"
          aria-label={`${pid} annual USD`}
        />
      </td>
      <td className="px-3 py-2 align-middle">
        <select
          className="h-8 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface)] px-2 text-sm text-[var(--fg)]"
          value={draft.billing_interval}
          onChange={(e) =>
            setDraft((d) => ({ ...d, billing_interval: e.target.value }))
          }
          aria-label={`${pid} billing interval`}
        >
          <option value="monthly">Monthly</option>
          <option value="annual">Annual</option>
          <option value="both">Both</option>
        </select>
      </td>
      <td className="px-3 py-2 align-middle">
        <Input
          type="number"
          min={0}
          max={30}
          value={draft.grace_period_days}
          onChange={(e) =>
            setDraft((d) => ({ ...d, grace_period_days: e.target.value }))
          }
          className="h-8 max-w-[4.5rem] font-mono text-sm"
          aria-label={`${pid} grace days`}
        />
      </td>
      <td className="px-3 py-2 align-middle text-right">
        <Button
          size="sm"
          variant="secondary"
          disabled={saving || !pid}
          onClick={() => {
            const body: Record<string, unknown> = {
              active: draft.active,
              billing_interval: draft.billing_interval,
            };
            const monthly = Number(draft.monthly_price_usd);
            if (Number.isFinite(monthly)) body.monthly_price_usd = monthly;
            const annual = Number(draft.annual_price_usd);
            if (Number.isFinite(annual)) body.annual_price_usd = annual;
            const grace = Number(draft.grace_period_days);
            if (Number.isFinite(grace)) body.grace_period_days = Math.round(grace);
            onSave(pid, body);
          }}
        >
          Save
        </Button>
      </td>
    </tr>
  );
}

export default function AdminPlansPage() {
  const { user } = useAuth();
  const allowed = canAccessIteOps(user);
  const qc = useQueryClient();

  const plansQ = useQuery({
    queryKey: ADMIN_PLANS_KEY,
    queryFn: () => billingApi.adminPlans(),
    enabled: allowed,
    retry: false,
    refetchInterval: 30_000,
  });

  const revenueQ = useQuery({
    queryKey: ADMIN_REVENUE_KEY,
    queryFn: () => billingApi.revenue(),
    enabled: allowed,
    retry: false,
    refetchInterval: 30_000,
  });

  const [savingPlanId, setSavingPlanId] = useState<string | null>(null);
  const [assignUserId, setAssignUserId] = useState("");
  const [assignPlanId, setAssignPlanId] = useState("");
  const [assignDays, setAssignDays] = useState("30");
  const [assignReason, setAssignReason] = useState("");
  const [assignOpen, setAssignOpen] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);

  const plansRoot = asRecord(plansQ.data);
  const allPlans = useMemo(
    () => asList(plansRoot.all_plans).map(asRecord),
    [plansQ.data],
  );

  const revenue = asRecord(revenueQ.data);
  const orders = useMemo(
    () => asList(revenue.orders).map(asRecord),
    [revenueQ.data],
  );

  const upsertMut = useMutation({
    mutationFn: ({ pid, body }: { pid: string; body: Record<string, unknown> }) =>
      billingApi.upsertPlan(pid, body),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ADMIN_PLANS_KEY });
    },
    onSettled: () => setSavingPlanId(null),
  });

  const assignMut = useMutation({
    mutationFn: () =>
      billingApi.assignPlan({
        user_id: assignUserId.trim(),
        plan_id: assignPlanId,
        days: Math.max(1, Math.round(Number(assignDays) || 30)),
        reason: assignReason.trim(),
      }),
    onSuccess: async () => {
      setAssignOpen(false);
      setAssignUserId("");
      setAssignReason("");
      setAssignError(null);
      await qc.invalidateQueries({ queryKey: ADMIN_REVENUE_KEY });
    },
    onError: (err: Error) => {
      setAssignError(err.message || "Assignment failed");
    },
  });

  const handleSavePlan = useCallback(
    (pid: string, body: Record<string, unknown>) => {
      setSavingPlanId(pid);
      upsertMut.mutate({ pid, body });
    },
    [upsertMut],
  );

  useEffect(() => {
    if (!assignPlanId && allPlans.length > 0) {
      setAssignPlanId(planId(allPlans[0] ?? {}));
    }
  }, [allPlans, assignPlanId]);

  if (!allowed) {
    return (
      <div className="min-w-0 space-y-4">
        <PageHeader
          eyebrow="Admin Portal"
          title="Plans & Subscriptions"
          description="SaaS catalog, revenue KPIs, and audited manual license grants."
        />
        <DeskError
          message={iteOpsAccessDeniedMessage(user, undefined, "Plans & Subscriptions")}
        />
      </div>
    );
  }

  const loading = (plansQ.isLoading && !plansQ.data) || (revenueQ.isLoading && !revenueQ.data);
  const loadError =
    (plansQ.error && !plansQ.data) || (revenueQ.error && !revenueQ.data);

  if (loading) {
    return (
      <div className="min-w-0 space-y-4">
        <PageHeader
          eyebrow="Admin Portal"
          title="Plans & Subscriptions"
          description="SaaS catalog, revenue KPIs, and audited manual license grants."
        />
        <DeskSkeleton rows={12} />
      </div>
    );
  }

  if (loadError) {
    const err = plansQ.error ?? revenueQ.error;
    return (
      <div className="min-w-0 space-y-4">
        <PageHeader
          eyebrow="Admin Portal"
          title="Plans & Subscriptions"
          description="SaaS catalog, revenue KPIs, and audited manual license grants."
        />
        <DeskError
          message={iteOpsAccessDeniedMessage(user, err, "Plans & Subscriptions")}
        />
      </div>
    );
  }

  const assignPreview = `Grant plan "${assignPlanId || "—"}" to user ${assignUserId.trim() || "—"} for ${assignDays} days. No paid order will be created — license grant only.`;

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        eyebrow="Admin Portal"
        title="Plans & Subscriptions"
        description="Live billing catalog and revenue from recorded orders only. Manual assignment is an audited license grant without inventing payments."
        actions={
          <Button asChild size="sm" variant="outline">
            <Link href="/admin/customer-ops#licenses">Licenses (COP)</Link>
          </Button>
        }
      />

      <PageMotion>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="Paid revenue (USD)"
            value={fmtUsd(revenue.revenue_usd_paid)}
          />
          <KpiCard
            label="Paid orders"
            value={String(revenue.paid_orders ?? 0)}
          />
          <KpiCard
            label="Pending orders"
            value={String(revenue.pending_orders ?? 0)}
          />
          <KpiCard
            label="Active licenses"
            value={String(revenue.active_licenses ?? 0)}
          />
        </div>

        {allPlans.length === 0 ? (
          <DeskEmpty
            icon={CreditCard}
            title="No plans"
            description="The billing catalog returned no plans from the API."
          />
        ) : (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Plan catalog</CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0">
              <div className="overflow-x-auto rounded-[var(--radius-os)] border border-[var(--border)]">
                <table className="w-full text-left text-sm">
                  <thead className="sticky top-0 bg-[var(--surface-2)]/95 text-[var(--fg-subtle)] backdrop-blur">
                    <tr>
                      {[
                        "Plan",
                        "Active",
                        "Monthly USD",
                        "Annual USD",
                        "Interval",
                        "Grace days",
                        "Actions",
                      ].map((c) => (
                        <th
                          key={c}
                          className="px-3 py-2 text-[10px] font-medium uppercase tracking-[0.08em]"
                        >
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {allPlans.map((row) => (
                      <PlanRowEditor
                        key={planId(row)}
                        row={row}
                        saving={savingPlanId === planId(row) && upsertMut.isPending}
                        onSave={handleSavePlan}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Assign plan (manual license)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-[var(--fg-muted)]">
              Designated owner only on the API. Creates an audited license grant —
              never fabricates a paid billing order.
            </p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <label className="flex flex-col gap-1 text-xs text-[var(--fg-subtle)]">
                User ID
                <Input
                  value={assignUserId}
                  onChange={(e) => setAssignUserId(e.target.value)}
                  placeholder="UUID"
                  className="font-mono text-sm"
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-[var(--fg-subtle)]">
                Plan
                <select
                  className="h-9 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface)] px-2 text-sm text-[var(--fg)]"
                  value={assignPlanId}
                  onChange={(e) => setAssignPlanId(e.target.value)}
                >
                  {allPlans.map((p) => {
                    const id = planId(p);
                    return (
                      <option key={id} value={id}>
                        {str(p.name, id)}
                      </option>
                    );
                  })}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-[var(--fg-subtle)]">
                Days
                <Input
                  type="number"
                  min={1}
                  max={3650}
                  value={assignDays}
                  onChange={(e) => setAssignDays(e.target.value)}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-[var(--fg-subtle)] sm:col-span-2 lg:col-span-4">
                Reason (audit)
                <Input
                  value={assignReason}
                  onChange={(e) => setAssignReason(e.target.value)}
                  placeholder="Support escalation, enterprise agreement, …"
                />
              </label>
            </div>
            {assignError ? (
              <p className="text-sm text-[var(--danger)]" role="alert">
                {assignError}
              </p>
            ) : null}
            <Button
              size="sm"
              disabled={
                !assignUserId.trim() ||
                !assignPlanId ||
                assignReason.trim().length < 3 ||
                assignMut.isPending
              }
              onClick={() => {
                setAssignError(null);
                setAssignOpen(true);
              }}
            >
              Review assignment
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Recent orders</CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0">
            {orders.length === 0 ? (
              <p className="text-sm text-[var(--fg-muted)]">
                No billing orders recorded.
              </p>
            ) : (
              <DeskTable
                columns={["Order", "Status", "Plan", "Amount", "Created"]}
                rows={orders.map((o) => {
                  const code = str(o.order_code, "—");
                  const status = str(o.status, "—").toUpperCase();
                  return [
                    <span key={`${code}-code`} className="font-mono text-xs">
                      {code}
                    </span>,
                    <Badge
                      key={`${code}-status`}
                      tone={
                        status === "PAID"
                          ? "success"
                          : status.includes("PENDING") || status === "CONFIRMING"
                            ? "warning"
                            : "neutral"
                      }
                    >
                      {status}
                    </Badge>,
                    str(o.plan_id, "—"),
                    `${fmtUsd(o.amount_usd)} ${str(o.currency, "")}`.trim(),
                    str(o.created_at ?? o.paid_at, "—"),
                  ];
                })}
              />
            )}
          </CardContent>
        </Card>
      </PageMotion>

      <ConfirmDialog
        open={assignOpen}
        onOpenChange={setAssignOpen}
        title="Confirm license assignment"
        description={assignPreview}
        confirmLabel="Assign license"
        busy={assignMut.isPending}
        onConfirm={async () => {
          await assignMut.mutateAsync();
        }}
      />
    </div>
  );
}
