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
      { href: "/ops", label: "Robot operations", hint: "Start · pause · stop · kill switch" },
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
      { href: "/execution", label: "OMS", hint: "Order management" },
    ],
  },
  {
    title: "Research",
    items: [
      { href: "/research", label: "Market research diagnostics", hint: "Universe and research" },
      { href: "/market-scanner", label: "Scanner diagnostics", hint: "Scanner internals" },
      { href: "/strategy-diagnostics", label: "Strategy diagnostics", hint: "Why NO_TRADE" },
    ],
  },
  {
    title: "System",
    items: [
      { href: "/monitoring", label: "Health", hint: "Health · latency" },
      { href: "/admin/customer-ops", label: "Audit", hint: "Users and account operations" },
      { href: "/logs", label: "Deployment / system diagnostics", hint: "Operational logs" },
    ],
  },
] as const;

export default function AdminPortalPage() {
  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        title="Admin"
        description="Internal operations. Trader desks stay on Home, Markets, and Terminal. Backend roles still enforce these routes."
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
