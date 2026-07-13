"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { brokerConnectivityApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";

const CHECK_COLS = [
  "login",
  "account_sync",
  "balances",
  "equity",
  "positions",
  "pending_orders",
  "history",
  "symbols",
  "quotes",
  "candles",
  "paper_trading",
  "execution_checks",
] as const;

function toneFor(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "compatible") return "success";
  if (status === "pending_session" || status === "documented") return "warning";
  if (status === "error") return "danger";
  return "neutral";
}

export default function BrokerCompatibilityPage() {
  const [slug, setSlug] = useState("weltrade");

  const dashQ = useQuery({
    queryKey: ["broker-compatibility-dashboard"],
    queryFn: brokerConnectivityApi.compatibilityDashboard,
    retry: false,
  });

  const onboardingQ = useQuery({
    queryKey: ["broker-onboarding", slug],
    queryFn: () => brokerConnectivityApi.onboarding(slug),
    retry: false,
  });

  const data = asRecord(dashQ.data);
  const session = asRecord(data.session);
  const matrix = asList(data.matrix).map(asRecord);
  const brokers = asList(data.brokers).map(asRecord);
  const actions = asList(data.operator_actions).map(String);
  const guide = asRecord(onboardingQ.data);
  const steps = asList(guide.steps).map(asRecord);
  const selected =
    brokers.find((b) => str(b.slug) === slug) ?? asRecord({});

  return (
    <div>
      <PageHeader
        title="Broker Compatibility"
        description="MT5 ecosystem v1.1 — Weltrade, XM, Exness, IC Markets, Pepperstone. Live probes only; never simulated."
        actions={
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" asChild>
              <Link href="/mt5">Connect MT5</Link>
            </Button>
            <Button size="sm" variant="secondary" onClick={() => dashQ.refetch()}>
              Refresh
            </Button>
          </div>
        }
      />

      {dashQ.isLoading ? (
        <DeskSkeleton rows={6} />
      ) : dashQ.isError ? (
        <DeskError
          message="Compatibility dashboard unavailable."
          onRetry={() => dashQ.refetch()}
        />
      ) : (
        <div className="space-y-4">
          <p className="text-xs text-[var(--fg-subtle)]">{str(data.notes)}</p>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="MT5 connected"
              value={session.connected ? "yes" : "no"}
              hint={str(session.server) || "No live session"}
            />
            <StatCard
              label="Matched brand"
              value={str(session.matched_broker) || "n/a"}
              hint="From live server string"
            />
            <StatCard
              label="Priority brokers"
              value={String(matrix.length)}
              hint="Ecosystem v1.1"
            />
            <StatCard
              label="EXECUTION_ENABLED"
              value={String(Boolean(session.execution_enabled))}
              hint="Read-only — never flipped here"
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Compatibility matrix</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <DeskTable
                columns={["Broker", "Overall", ...CHECK_COLS]}
                rows={matrix.map((row) => [
                  <button
                    key="b"
                    type="button"
                    className="text-left font-medium underline-offset-2 hover:underline"
                    onClick={() => setSlug(str(row.slug))}
                  >
                    {str(row.name)}
                    {row.session_matched ? (
                      <Badge className="ml-2" tone="success">
                        session
                      </Badge>
                    ) : null}
                  </button>,
                  <Badge key="o" tone={toneFor(str(row.overall))}>
                    {str(row.overall)}
                  </Badge>,
                  ...CHECK_COLS.map((c) => (
                    <Badge key={c} tone={toneFor(str(row[c]))}>
                      {str(row[c]) || "—"}
                    </Badge>
                  )),
                ])}
              />
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>
                  Onboarding — {str(guide.name) || slug}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  {brokers.map((b) => (
                    <Button
                      key={str(b.slug)}
                      size="sm"
                      variant={slug === str(b.slug) ? "default" : "secondary"}
                      onClick={() => setSlug(str(b.slug))}
                    >
                      {str(b.name)}
                    </Button>
                  ))}
                </div>
                <p className="text-xs text-[var(--fg-subtle)]">
                  Website:{" "}
                  <a
                    className="underline"
                    href={str(guide.website)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {str(guide.website)}
                  </a>
                </p>
                <ol className="list-decimal space-y-2 pl-5 text-sm">
                  {steps.map((s, i) => (
                    <li key={`${str(s.title)}-${i}`}>
                      <div className="font-medium">{str(s.title)}</div>
                      <div className="text-[var(--fg-subtle)]">{str(s.detail)}</div>
                    </li>
                  ))}
                </ol>
                <div className="text-xs text-[var(--fg-subtle)]">
                  Server hints (not auto-login):{" "}
                  {asList(guide.server_hints).map(String).join(", ") || "—"}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Selected broker checks</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex flex-wrap gap-2">
                  <Badge tone={selected.session_matched ? "success" : "neutral"}>
                    session_matched={String(Boolean(selected.session_matched))}
                  </Badge>
                  <Badge tone={toneFor(str(asRecord(selected.summary).overall))}>
                    {str(asRecord(selected.summary).overall) || "—"}
                  </Badge>
                </div>
                <DeskTable
                  columns={["Check", "Status", "Detail"]}
                  rows={asList(selected.checks)
                    .map(asRecord)
                    .map((c) => [
                      str(c.check),
                      <Badge key="s" tone={toneFor(str(c.status))}>
                        {str(c.status)}
                      </Badge>,
                      str(c.detail) || "—",
                    ])}
                />
                <div>
                  <div className="mb-1 text-xs text-[var(--fg-subtle)]">
                    Remaining operator actions
                  </div>
                  <ul className="list-disc space-y-1 pl-5 text-xs">
                    {actions.map((a, i) => (
                      <li key={i}>{a}</li>
                    ))}
                  </ul>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
