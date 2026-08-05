"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Brain,
  FileText,
  LayoutDashboard,
  LineChart,
  NotebookPen,
  Radar,
  Shield,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getApiConnectionState } from "@/lib/api/connectivity";
import {
  platformApi,
  portfolioApi,
  signalCenterApi,
} from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { useLiveTrades } from "@/hooks/use-live-trades";
import { useTradingSession } from "@/providers/trading-session-provider";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { cn } from "@/lib/utils";

const ACTIONS = [
  { href: "/mission-control", label: "Mission Control", icon: Radar },
  { href: "/terminal", label: "Terminal", icon: LayoutDashboard },
  { href: "/portfolio-intelligence", label: "Portfolio Intel", icon: LineChart },
  { href: "/trading-journal", label: "Journal", icon: NotebookPen },
  { href: "/daily-reports", label: "Reports", icon: FileText },
  { href: "/ai-coach", label: "AI Coach", icon: Brain },
  { href: "/risk-center", label: "Risk", icon: Shield },
] as const;

function Card({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "ok" | "bad" | "neutral";
}) {
  return (
    <div className="border border-[var(--border)] bg-[var(--surface)] px-3 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p
        className={cn(
          "mt-1 font-mono text-[17px] tabular",
          tone === "ok" && "text-[var(--success)]",
          tone === "bad" && "text-[var(--danger)]",
          (!tone || tone === "neutral") && "text-[var(--fg)]",
        )}
      >
        {value}
      </p>
    </div>
  );
}

/** RC3 Executive Home — CEO intelligence desk from LIVE feeds only. */
export function ExecutiveHomeWorkspace() {
  const session = useTradingSession();
  const month = useLiveTrades("month");
  const week = useLiveTrades("week");
  const today = useLiveTrades("today");

  const signalsQ = useQuery({
    queryKey: ["signals-center", "executive-home"],
    queryFn: () => signalCenterApi.list({}),
    staleTime: 45_000,
    refetchInterval: 90_000,
    retry: false,
  });
  const ordersQ = useQuery({
    queryKey: ["portfolio-orders", "executive-home"],
    queryFn: () => portfolioApi.orders(),
    staleTime: 20_000,
    refetchInterval: 40_000,
    retry: false,
  });
  const healthQ = useQuery({
    queryKey: ["platform-health", "executive-home"],
    queryFn: platformApi.health,
    staleTime: 45_000,
    refetchInterval: 60_000,
    retry: 1,
  });

  const equity = num(session.equity, NaN);
  const balance = num(session.balance, NaN);
  const growthPct =
    Number.isFinite(equity) && Number.isFinite(balance) && balance !== 0
      ? ((equity - balance) / Math.abs(balance)) * 100
      : null;

  const todayPnl = today.analytics.todayPl;
  const weekPnl = week.analytics.weekPl;
  const monthPnl = month.analytics.monthPl;

  const symbols = useMemo(() => {
    const set = new Set<string>();
    for (const p of session.positions) {
      const s = str(asRecord(p).symbol).toUpperCase();
      if (s) set.add(s);
    }
    return set.size;
  }, [session.positions]);

  const dash = asRecord(asRecord(signalsQ.data).dashboard);
  const signalItems = asList(
    asRecord(signalsQ.data).items ||
      asRecord(signalsQ.data).signals ||
      signalsQ.data,
  );
  const avgConf = (() => {
    const vals = signalItems
      .map((r) => num(asRecord(r).confidence ?? asRecord(r).confidence_score, NaN))
      .filter((n) => Number.isFinite(n));
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  })();

  const ordersToday = asList(ordersQ.data).length;
  const apiState = getApiConnectionState();
  const systemHealth =
    apiState === "unreachable"
      ? "Unreachable"
      : apiState === "degraded"
        ? "Degraded"
        : healthQ.isSuccess
          ? "Healthy"
          : healthQ.isLoading
            ? "Checking"
            : "Unknown";

  const riskLabel =
    session.positions.length === 0
      ? "Flat"
      : Math.abs(
            session.positions.reduce((s, p) => s + num(asRecord(p).profit, 0), 0),
          ) >
          Math.abs(equity || 0) * 0.02
        ? "Elevated float"
        : "Contained";

  const fmtMoney = (v: number) =>
    Number.isFinite(v) ? formatNumber(v, 2) : "—";
  const toneOf = (v: number): "ok" | "bad" | "neutral" =>
    !Number.isFinite(v) ? "neutral" : v >= 0 ? "ok" : "bad";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge tone={session.connected ? "success" : "warning"} className="h-5">
            {session.connected ? "LIVE capital" : "Session limited"}
          </Badge>
          <span className="text-[12px] text-[var(--fg-muted)]">
            Intelligence OS · recommendations & analytics only
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {ACTIONS.map((a) => {
            const Icon = a.icon;
            return (
              <Button key={a.href} asChild size="sm" variant="outline">
                <Link href={a.href}>
                  <Icon className="mr-1 h-3.5 w-3.5" />
                  {a.label}
                </Link>
              </Button>
            );
          })}
        </div>
      </div>

      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <Card label="Today's Profit" value={fmtMoney(todayPnl)} tone={toneOf(todayPnl)} />
        <Card label="Weekly Profit" value={fmtMoney(weekPnl)} tone={toneOf(weekPnl)} />
        <Card label="Monthly Profit" value={fmtMoney(monthPnl)} tone={toneOf(monthPnl)} />
        <Card
          label="Current Capital"
          value={Number.isFinite(equity) ? formatCurrency(equity) : "—"}
        />
        <Card
          label="Growth %"
          value={growthPct != null ? `${growthPct.toFixed(2)}%` : "—"}
          tone={growthPct == null ? "neutral" : growthPct >= 0 ? "ok" : "bad"}
        />
        <Card
          label="Win Rate"
          value={
            month.analytics.winRate != null
              ? `${(month.analytics.winRate * 100).toFixed(1)}%`
              : "—"
          }
        />
        <Card
          label="Profit Factor"
          value={
            month.analytics.profitFactor != null
              ? formatNumber(month.analytics.profitFactor, 2)
              : "—"
          }
        />
        <Card
          label="Average RR"
          value={
            month.analytics.averageRr != null
              ? formatNumber(month.analytics.averageRr, 2)
              : "—"
          }
        />
        <Card
          label="Average Hold"
          value={
            month.analytics.avgHoldMs != null
              ? `${Math.round(month.analytics.avgHoldMs / 60000)}m`
              : "—"
          }
        />
        <Card label="Open Positions" value={String(session.positions.length)} />
        <Card label="Active Symbols" value={String(symbols)} />
        <Card
          label="Signals Today"
          value={str(dash.total_signals ?? signalItems.length, "—")}
        />
        <Card label="Orders Today" value={String(ordersToday)} />
        <Card
          label="AI Confidence"
          value={avgConf != null ? formatNumber(avgConf, 2) : "—"}
        />
        <Card label="Portfolio Risk" value={riskLabel} />
        <Card
          label="System Health"
          value={systemHealth}
          tone={
            systemHealth === "Healthy"
              ? "ok"
              : systemHealth === "Degraded" || systemHealth === "Unreachable"
                ? "bad"
                : "neutral"
          }
        />
      </dl>
    </div>
  );
}
