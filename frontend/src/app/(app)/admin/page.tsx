"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const ADMIN_SECTIONS = [
  {
    title: "Operations",
    items: [
      { href: "/ops", label: "Execution sessions", hint: "Robot run state · control plane" },
      { href: "/admin/customer-ops", label: "Account bindings", hint: "Owned broker accounts" },
      { href: "/ops", label: "Robot operations", hint: "Institutional robot controls" },
      { href: "/risk-center", label: "Trading controls", hint: "Risk locks and desk controls" },
    ],
  },
  {
    title: "Broker Infrastructure",
    items: [
      { href: "/gateway", label: "Gateway diagnostics", hint: "MT5 gateway connectivity" },
      { href: "/broker-connectivity", label: "Broker health", hint: "Connection health" },
      { href: "/execution/diagnostics", label: "Connection diagnostics", hint: "Session diagnostics" },
    ],
  },
  {
    title: "Research",
    items: [
      { href: "/research", label: "Research engine status", hint: "Universe worker and diagnostics" },
      { href: "/markets", label: "Universe discovery", hint: "Broker catalogue instruments" },
      { href: "/signals", label: "Analysis coverage", hint: "Global market intelligence desk" },
      { href: "/signal-center", label: "Signal health", hint: "Operator signal board" },
    ],
  },
  {
    title: "Safety",
    items: [
      { href: "/admin/reliability", label: "Safety gates", hint: "research_can_execute · promotion · OMS" },
      { href: "/execution", label: "OMS status", hint: "Order management (authorized only)" },
      { href: "/portfolio", label: "Live orders / positions", hint: "Owned account exposure" },
      { href: "/strategy-diagnostics", label: "Trading blockers", hint: "Why NO_TRADE" },
    ],
  },
  {
    title: "System Health",
    items: [
      { href: "/monitoring", label: "API health", hint: "Health · latency · readiness" },
      { href: "/admin/noc", label: "Worker health", hint: "NOC operations command" },
      { href: "/logs", label: "Deployment diagnostics", hint: "Operational logs" },
      { href: "/admin/customer-ops", label: "Audit", hint: "Users and account operations" },
    ],
  },
] as const;

export default function AdminPortalPage() {
  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        title="Internal Trading Operations"
        description="Dedicated QuantForg operations console. Not part of the trader desk. Backend RBAC (OWNER / ADMIN) remains enforced independently of this UI."
      />
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
                    className="flex min-w-0 flex-col rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3 transition hover:border-[var(--accent)] hover:bg-[var(--accent-soft)]"
                  >
                    <span className="text-sm font-medium text-[var(--fg)]">
                      {item.label}
                    </span>
                    <span className="text-xs text-[var(--fg-subtle)]">{item.hint}</span>
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
