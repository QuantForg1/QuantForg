"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const ADMIN_SECTIONS = [
  {
    title: "Operations",
    items: [
      { href: "/admin/noc", label: "NOC / Operations", hint: "Live production desk" },
      { href: "/ops", label: "Control plane", hint: "Kill switch · auto-trading" },
      { href: "/mission-control", label: "Mission Control", hint: "Burn-in and status" },
    ],
  },
  {
    title: "Risk",
    items: [
      { href: "/risk-center", label: "Risk center", hint: "Risk locks and limits" },
      { href: "/risk-lab", label: "Risk lab", hint: "Risk analysis" },
    ],
  },
  {
    title: "Safety",
    items: [
      { href: "/admin/reliability", label: "Reliability", hint: "Production reliability program" },
      { href: "/live-alerts", label: "Live alerts", hint: "Safety and runtime alerts" },
    ],
  },
  {
    title: "Execution",
    items: [
      { href: "/admin/live-trading-evidence", label: "Live evidence", hint: "Execution evidence" },
      { href: "/execution-intel", label: "Execution intelligence", hint: "Fill quality" },
      { href: "/trading-kernel", label: "Trading kernel", hint: "Runtime controls" },
    ],
  },
  {
    title: "OMS",
    items: [
      { href: "/execution", label: "OMS / execution", hint: "Order management — owner/admin" },
      { href: "/execution/diagnostics", label: "Execution diagnostics", hint: "Session and fill diagnostics" },
      { href: "/executions", label: "Execution history", hint: "Historical execution records" },
    ],
  },
  {
    title: "Execution sessions",
    items: [
      { href: "/gateway", label: "Active terminal session", hint: "Singleton GatewayMT5Client / one Windows terminal" },
      { href: "/ops", label: "Robot run state", hint: "Global auto-trade run state · owner/admin" },
    ],
  },
  {
    title: "Account bindings",
    items: [
      { href: "/admin/customer-ops", label: "Owned accounts", hint: "User-owned broker accounts" },
      { href: "/broker", label: "Your binding", hint: "Authenticated session bind — never another user" },
    ],
  },
  {
    title: "Broker infrastructure",
    items: [
      { href: "/gateway", label: "Gateway diagnostics", hint: "MT5 gateway connectivity" },
      { href: "/broker-connectivity", label: "Broker connectivity", hint: "Connection diagnostics" },
      { href: "/execution/diagnostics", label: "Session diagnostics", hint: "Execution / session diagnostics" },
    ],
  },
  {
    title: "System health",
    items: [
      { href: "/monitoring", label: "Monitoring", hint: "Health · latency" },
      { href: "/logs", label: "System logs", hint: "Operational log stream" },
    ],
  },
  {
    title: "Audit",
    items: [
      { href: "/admin/customer-ops", label: "Users / customer ops", hint: "Account operations" },
      { href: "/admin/enterprise", label: "Enterprise", hint: "Platform controls" },
    ],
  },
  {
    title: "Research diagnostics",
    items: [
      { href: "/research", label: "Research", hint: "Market universe / research" },
      { href: "/research-lab", label: "Research lab", hint: "Research internals" },
    ],
  },
] as const;

export default function AdminPortalPage() {
  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        title="Admin"
        description="Internal operations only. Trader desks stay on Home. Backend roles still enforce these routes."
      />
      {ADMIN_SECTIONS.map((section) => (
        <Card key={section.title}>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>{section.title}</CardTitle>
            <Badge tone="warning">Owner / admin</Badge>
          </CardHeader>
          <CardContent>
            <ul className="grid gap-2 sm:grid-cols-2">
              {section.items.map((item) => (
                <li key={item.href}>
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
