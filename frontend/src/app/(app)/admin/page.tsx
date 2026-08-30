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
      { href: "/admin/noc", label: "NOC", hint: "Network operations command" },
    ],
  },
  {
    title: "Broker infrastructure",
    items: [
      { href: "/gateway", label: "Gateway diagnostics", hint: "MT5 gateway connectivity" },
      { href: "/broker-connectivity", label: "Broker health", hint: "Connection health" },
      { href: "/execution/diagnostics", label: "Connection diagnostics", hint: "Session diagnostics" },
    ],
  },
  {
    title: "Trading control",
    items: [
      { href: "/risk-center", label: "Risk", hint: "Risk locks and limits" },
      { href: "/admin/reliability", label: "Safety", hint: "Reliability and safety ops" },
      { href: "/execution", label: "OMS", hint: "Order management (authorized only)" },
    ],
  },
  {
    title: "Research monitoring",
    items: [
      { href: "/signals", label: "Trader Signals", hint: "Advisory market intelligence" },
      { href: "/signal-center", label: "Signal Center", hint: "Operator XAUUSD scan board" },
      { href: "/research", label: "Research diagnostics", hint: "Universe and research worker" },
      { href: "/strategy-diagnostics", label: "Strategy diagnostics", hint: "Why NO_TRADE" },
    ],
  },
  {
    title: "System",
    items: [
      { href: "/monitoring", label: "Health", hint: "Health · latency" },
      { href: "/admin/customer-ops", label: "Audit", hint: "Users and account operations" },
      { href: "/logs", label: "Deployment diagnostics", hint: "Operational logs" },
    ],
  },
] as const;

export default function AdminPortalPage() {
  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        title="Operations / Admin"
        description="Internal QuantForg control surfaces. Not part of the trader desk navigation. Backend RBAC remains enforced."
      />
      <div className="grid gap-3 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Safety</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs text-[var(--fg-muted)]">
            <p>Research stays advisory</p>
            <p>Live trading requires explicit authorization</p>
            <Badge tone="neutral">OMS not enabled by Admin</Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Access</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs text-[var(--fg-muted)]">
            <p>OWNER / ADMIN only</p>
            <p>Trader sidebar never links here</p>
            <Badge tone="warning">Protected route</Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Research</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs text-[var(--fg-muted)]">
            <p>Global catalogue discovery</p>
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
