"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowUpRight } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { EquityChart } from "@/components/charts/equity-chart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { mt5Api, portfolioApi, platformApi } from "@/lib/api/endpoints";
import { formatCurrency } from "@/lib/utils";

export default function DashboardPage() {
  const portfolio = useQuery({
    queryKey: ["portfolio"],
    queryFn: portfolioApi.get,
    retry: false,
  });
  const mt5 = useQuery({ queryKey: ["mt5-status"], queryFn: mt5Api.status, retry: false });
  const version = useQuery({ queryKey: ["version"], queryFn: platformApi.version });

  const account = (portfolio.data?.account || {}) as Record<string, unknown>;
  const positions = (portfolio.data?.positions as unknown[]) || [];

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Realtime desk overview — equity, risk, alerts, and quick actions."
        actions={
          <>
            <Button variant="secondary" asChild>
              <Link href="/mt5">MT5 status</Link>
            </Button>
            <Button asChild>
              <Link href="/execution">
                Trade <ArrowUpRight className="h-4 w-4" />
              </Link>
            </Button>
          </>
        }
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Balance"
          value={account.balance != null ? formatCurrency(String(account.balance)) : "—"}
          hint="Synced from MT5 when connected"
        />
        <StatCard
          label="Equity"
          value={account.equity != null ? formatCurrency(String(account.equity)) : "—"}
          tone="up"
        />
        <StatCard
          label="Open positions"
          value={String(portfolio.data?.position_count ?? positions.length ?? "—")}
        />
        <StatCard
          label="MT5"
          value={mt5.data?.connected ? "Connected" : "Offline"}
          hint={String(mt5.data?.server || "No live terminal session")}
          tone={mt5.data?.connected ? "up" : "neutral"}
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.4fr_0.8fr]">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Portfolio curve</CardTitle>
            <Badge tone="accent">Live desk</Badge>
          </CardHeader>
          <CardContent>
            {portfolio.isLoading ? <Skeleton className="h-64 w-full" /> : <EquityChart />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Quick actions</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2">
            {[
              ["/execution", "Open order ticket"],
              ["/risk", "Run risk check"],
              ["/paper", "Paper trade"],
              ["/ai", "Ask AI assistant"],
            ].map(([href, label]) => (
              <Button key={href} variant="secondary" className="justify-start" asChild>
                <Link href={href}>{label}</Link>
              </Button>
            ))}
            <p className="pt-2 text-xs text-[var(--fg-subtle)]">
              API {String(version.data?.version || "…")} · execution remains disabled until enabled server-side
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent positions</CardTitle>
          </CardHeader>
          <CardContent>
            {portfolio.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : positions.length === 0 ? (
              <EmptyState
                icon={AlertTriangle}
                title="No open positions"
                description="Connect MT5 and sync portfolio to populate live exposure."
                actionLabel="Connect MT5"
                onAction={() => {
                  window.location.href = "/mt5";
                }}
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-[var(--fg-subtle)]">
                    <tr>
                      <th className="pb-2 font-medium">Symbol</th>
                      <th className="pb-2 font-medium">Volume</th>
                      <th className="pb-2 font-medium">Profit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.slice(0, 6).map((row, idx) => {
                      const p = row as Record<string, unknown>;
                      return (
                        <tr key={idx} className="border-t border-[var(--border)]">
                          <td className="py-2">{String(p.symbol ?? "—")}</td>
                          <td className="tabular py-2">{String(p.volume ?? "—")}</td>
                          <td className="tabular py-2">{String(p.profit ?? "—")}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Risk & alerts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3">
              <p className="text-sm font-medium">Risk score</p>
              <p className="mt-1 text-xs text-[var(--fg-muted)]">
                Connect portfolio context to evaluate leverage, margin, and policy gates.
              </p>
            </div>
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3">
              <p className="text-sm font-medium">Drawdown watch</p>
              <p className="mt-1 text-xs text-[var(--fg-muted)]">
                Performance analytics derive from synchronized equity history once available.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
