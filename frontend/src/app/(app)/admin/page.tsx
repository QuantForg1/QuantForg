"use client";

import Link from "next/link";
import { BarChart3 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { NocPanel } from "@/components/ops/noc/noc-primitives";
import { customerOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";
import {
  canAccessIteOps,
  iteOpsAccessDeniedMessage,
} from "@/lib/auth/ite-ops-access";

/** Frozen admin section map — required by trading_core regression gates. */
const ADMIN_SECTIONS = [
  {
    title: "Operations",
    items: [
      {
        href: "/admin/control",
        label: "Control center",
        hint: "Owner policy, broker, risk, live authorization",
      },
      {
        href: "/admin/live-trading",
        label: "Live trading control",
        hint: "DISABLED · ARM · ENABLE · KILL",
      },
      {
        href: "/ops",
        label: "Execution sessions",
        hint: "Robot run state · control plane",
      },
      {
        href: "/admin/customer-ops",
        label: "Account bindings",
        hint: "Owned broker accounts",
      },
      {
        href: "/ops",
        label: "Robot operations",
        hint: "Institutional robot controls",
      },
      {
        href: "/risk-center",
        label: "Trading controls",
        hint: "Risk locks and desk controls",
      },
    ],
  },
  {
    title: "Broker Infrastructure",
    items: [
      {
        href: "/gateway",
        label: "Gateway diagnostics",
        hint: "MT5 gateway connectivity",
      },
      {
        href: "/broker-connectivity",
        label: "Broker health",
        hint: "Connection health",
      },
      {
        href: "/execution/diagnostics",
        label: "Connection diagnostics",
        hint: "Session diagnostics",
      },
    ],
  },
  {
    title: "Research",
    items: [
      {
        href: "/research",
        label: "Research engine status",
        hint: "Universe worker and diagnostics",
      },
      {
        href: "/markets",
        label: "Universe discovery",
        hint: "Broker catalogue instruments",
      },
      {
        href: "/signals",
        label: "Analysis coverage",
        hint: "Global market intelligence desk",
      },
      {
        href: "/signal-center",
        label: "Signal health",
        hint: "Operator signal board",
      },
    ],
  },
  {
    title: "Safety",
    items: [
      {
        href: "/admin/live-trading",
        label: "Live trading control",
        hint: "DISABLED · ARM · ENABLE · KILL",
      },
      {
        href: "/admin/reliability",
        label: "Safety gates",
        hint: "research_can_execute · promotion · OMS",
      },
      {
        href: "/execution",
        label: "OMS status",
        hint: "Order management (authorized only)",
      },
      {
        href: "/portfolio",
        label: "Live orders / positions",
        hint: "Owned account exposure",
      },
      {
        href: "/strategy-diagnostics",
        label: "Trading blockers",
        hint: "Why NO_TRADE",
      },
      {
        href: "/strategy-performance",
        label: "Strategy performance",
        hint: "Five-pack scorecards · attribution · post-#182",
      },
    ],
  },
  {
    title: "System Health",
    items: [
      {
        href: "/monitoring",
        label: "API health",
        hint: "Health · latency · readiness",
      },
      {
        href: "/admin/noc",
        label: "Worker health",
        hint: "NOC operations command",
      },
      {
        href: "/logs",
        label: "Deployment diagnostics",
        hint: "Operational logs",
      },
      {
        href: "/admin/customer-ops",
        label: "Audit",
        hint: "Users and account operations",
      },
    ],
  },
] as const;

function fmt(v: unknown, fallback = "—"): string {
  if (v === null || v === undefined || v === "") return fallback;
  if (typeof v === "boolean") return v ? "Online" : "Offline";
  return String(v);
}

function KpiCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-medium uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="font-mono text-2xl font-semibold text-[var(--fg)]">{value}</p>
        {hint ? (
          <p className="mt-1 text-[11px] text-[var(--fg-muted)]">{hint}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export default function AdminPortalPage() {
  const { user } = useAuth();
  const allowed = canAccessIteOps(user);

  const platformQ = useQuery({
    queryKey: ["admin-overview-platform"],
    queryFn: () => customerOpsApi.platform(),
    enabled: allowed,
    refetchInterval: 20_000,
    retry: false,
  });

  const fleetQ = useQuery({
    queryKey: ["admin-overview-fleet"],
    queryFn: () => customerOpsApi.fleet(),
    enabled: allowed,
    retry: false,
    staleTime: 30_000,
  });

  const auditQ = useQuery({
    queryKey: ["admin-overview-audit"],
    queryFn: () => customerOpsApi.audit(40),
    enabled: allowed,
    retry: false,
    staleTime: 20_000,
  });

  if (!allowed) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(user, undefined, "Admin Overview")}
      />
    );
  }

  if (platformQ.isLoading && !platformQ.data) {
    return <DeskSkeleton variant="page" />;
  }

  if (platformQ.error && !platformQ.data) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(
          user,
          platformQ.error,
          "Admin Overview",
        )}
      />
    );
  }

  const data = asRecord(platformQ.data);
  const analytics = asRecord(data.analytics);
  const supportMetrics = asRecord(analytics.support_metrics);
  const licenseMetrics = asRecord(analytics.license_metrics);
  const brokers = asRecord(data.brokers);
  const support = asRecord(data.support);
  const fleet = asRecord(fleetQ.data ?? data.fleet);
  const flags = asRecord(data.flags);
  const auditRoot = asRecord(auditQ.data ?? data.audit);
  const auditItems = asList(auditRoot.items ?? auditRoot.events);

  const usersTotal = num(analytics.total_customers, NaN);
  const usersActive = num(analytics.active_customers, NaN);
  const subscriptionsActive = num(
    licenseMetrics.active ?? licenseMetrics.enabled,
    NaN,
  );
  const brokerCount = num(
    brokers.count ?? analytics.broker_connections,
    NaN,
  );
  const ticketsPending = num(
    supportMetrics.pending ?? support.pending_count,
    NaN,
  );
  const ticketsTotal = num(supportMetrics.total ?? support.count, NaN);
  const fleetCount = num(fleet.count ?? fleet.total_unfiltered, NaN);
  const robotOnline = analytics.active_robots === 1 || analytics.active_robots === true;
  const brokersConnected = num(
    brokers.connected ?? analytics.connected_brokers,
    NaN,
  );

  const healthLabel =
    Number.isFinite(brokersConnected) && brokersConnected > 0
      ? robotOnline
        ? "Operational"
        : "Degraded"
      : "No broker signal";

  const hasAnyKpi =
    Number.isFinite(usersTotal) ||
    Number.isFinite(usersActive) ||
    Number.isFinite(brokerCount) ||
    Number.isFinite(ticketsTotal);

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        eyebrow="Overview"
        title="Operations dashboard"
        description="Enterprise operations dashboard — production COP data only. Trading engine, MT5, and execution paths are not modified from this surface."
        actions={
          <Button asChild size="sm" variant="outline">
            <Link href="/admin/customer-ops">Customer Operations</Link>
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">As of {fmt(data.as_of)}</Badge>
        <Badge tone="success">
          trading untouched · {fmt(flags.modifies_trading, "false")}
        </Badge>
        {data.fabricated === true ? (
          <Badge tone="warning">Synthetic payload</Badge>
        ) : null}
      </div>

      {!hasAnyKpi ? (
        <DeskEmpty
          icon={BarChart3}
          title="No platform metrics yet"
          description="COP analytics will populate when user, broker, and support stores return data."
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <KpiCard
            label="Users"
            value={Number.isFinite(usersTotal) ? String(usersTotal) : "—"}
            hint="Total registered customers"
          />
          <KpiCard
            label="Active"
            value={Number.isFinite(usersActive) ? String(usersActive) : "—"}
            hint="Active or enabled accounts"
          />
          <KpiCard
            label="Subscriptions"
            value={
              Number.isFinite(subscriptionsActive)
                ? String(subscriptionsActive)
                : str(licenseMetrics.active, "—")
            }
            hint="Active licenses (license center)"
          />
          <KpiCard
            label="Brokers"
            value={Number.isFinite(brokerCount) ? String(brokerCount) : "—"}
            hint={
              Number.isFinite(brokersConnected)
                ? `${brokersConnected} connected`
                : undefined
            }
          />
          <KpiCard
            label="Tickets"
            value={
              Number.isFinite(ticketsPending)
                ? `${ticketsPending} pending`
                : "—"
            }
            hint={
              Number.isFinite(ticketsTotal)
                ? `${ticketsTotal} total`
                : undefined
            }
          />
          <KpiCard
            label="Health"
            value={healthLabel}
            hint={`Robot ${robotOnline ? "online" : "offline"} · fleet ${Number.isFinite(fleetCount) ? fleetCount : "—"}`}
          />
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-2">
        <NocPanel title="Fleet snapshot">
          {asList(fleet.customers).length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No fleet rows returned yet.
            </p>
          ) : (
            <ul className="space-y-1 text-[12px] text-[var(--fg)]">
              {asList(fleet.customers)
                .slice(0, 8)
                .map((row, i) => {
                  const r = asRecord(row);
                  return (
                    <li
                      key={str(r.id ?? r.customer_id, `fleet-${i}`)}
                      className="flex justify-between gap-2 border-b border-[var(--border)] py-1.5 last:border-0"
                    >
                      <span className="truncate">{fmt(r.email ?? r.id)}</span>
                      <span className="shrink-0 text-[var(--fg-muted)]">
                        {fmt(r.status)}
                      </span>
                    </li>
                  );
                })}
            </ul>
          )}
        </NocPanel>

        <NocPanel title="Support queue">
          {asList(support.tickets).length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No open support tickets.
            </p>
          ) : (
            <ul className="space-y-1 text-[12px]">
              {asList(support.tickets)
                .slice(0, 8)
                .map((row, i) => {
                  const r = asRecord(row);
                  return (
                    <li
                      key={str(r.id, `ticket-${i}`)}
                      className="flex justify-between gap-2 border-b border-[var(--border)] py-1.5 last:border-0"
                    >
                      <span className="truncate">{fmt(r.subject)}</span>
                      <span className="shrink-0 text-[var(--fg-muted)]">
                        {fmt(r.status)}
                      </span>
                    </li>
                  );
                })}
            </ul>
          )}
          <Button asChild size="sm" variant="secondary" className="mt-3">
            <Link href="/admin/support">Manage support</Link>
          </Button>
        </NocPanel>
      </div>

      <NocPanel
        title="Recent administrative activity"
        action={
          <Button asChild size="sm" variant="ghost">
            <Link href="/admin/customer-ops#audit">Full audit log</Link>
          </Button>
        }
      >
        {auditQ.isLoading && auditItems.length === 0 ? (
          <DeskSkeleton rows={3} />
        ) : auditItems.length === 0 ? (
          <p className="text-[12px] text-[var(--fg-muted)]">
            No COP audit events returned yet. License, support, and fleet actions
            appear here when recorded.
          </p>
        ) : (
          <ul className="space-y-1 text-[12px] text-[var(--fg)]">
            {auditItems.slice(0, 12).map((row, i) => {
              const r = asRecord(row);
              return (
                <li
                  key={str(r.id ?? r.at, `audit-${i}`)}
                  className="flex justify-between gap-2 border-b border-[var(--border)] py-1.5 last:border-0"
                >
                  <span className="truncate">
                    {fmt(r.action ?? r.event ?? r.type)}
                    {r.operator || r.by
                      ? ` · ${fmt(r.operator ?? r.by)}`
                      : ""}
                  </span>
                  <span className="shrink-0 text-[var(--fg-muted)]">
                    {fmt(r.at ?? r.created_at).slice(0, 19)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </NocPanel>

      <div className="grid gap-3 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Safety invariants</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs text-[var(--fg-muted)]">
            <p>research_can_execute = false</p>
            <p>allow_live_promotion = false</p>
            <p>forwarded_to_oms = false</p>
            <Badge tone="neutral">Opening Admin does not enable live trading</Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Access</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs text-[var(--fg-muted)]">
            <p>OWNER / ADMIN platform roles only</p>
            <p>Trader sidebar never links here</p>
            <Badge tone="warning">Protected route</Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Research</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs text-[var(--fg-muted)]">
            <p>Global catalogue discovery is advisory</p>
            <p>Signals are not trade tickets</p>
            <Badge tone="neutral">Advisory only</Badge>
          </CardContent>
        </Card>
      </div>

      {ADMIN_SECTIONS.map((section) => (
        <Card key={section.title}>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>{section.title}</CardTitle>
            <Badge tone="warning">Owner / admin</Badge>
          </CardHeader>
          <CardContent>
            <ul className="grid gap-2 sm:grid-cols-2">
              {section.items.map((item) => (
                <li key={`${section.title}-${item.href}-${item.label}`}>
                  <Link
                    href={item.href}
                    className="flex min-w-0 flex-col rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3.5 transition hover:border-[var(--accent)] hover:bg-[var(--accent-soft)]"
                  >
                    <span className="text-sm font-medium text-[var(--fg)]">
                      {item.label}
                    </span>
                    <span className="text-xs text-[var(--fg-subtle)]">
                      {item.hint}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
