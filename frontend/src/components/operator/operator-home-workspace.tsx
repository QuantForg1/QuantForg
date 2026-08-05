"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Brain,
  Gauge,
  LayoutDashboard,
  LineChart,
  ListOrdered,
  Radar,
  Shield,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PlatformStatusBoard } from "@/components/ops/platform-status-board";
import { useLiveTrades } from "@/hooks/use-live-trades";
import {
  ecosystemApi,
  portfolioApi,
  signalCenterApi,
} from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { useTradingSession } from "@/providers/trading-session-provider";
import { formatNumber } from "@/lib/utils";

const ACTIONS = [
  { href: "/mission-control", label: "Mission Control", icon: Radar },
  { href: "/terminal", label: "Terminal", icon: LayoutDashboard },
  { href: "/trading-journal", label: "Trading Journal", icon: LineChart },
  { href: "/ai-coach", label: "AI Coach", icon: Brain },
  { href: "/daily-reports", label: "Daily Reports", icon: Gauge },
  { href: "/order-monitor", label: "Order Monitor", icon: ListOrdered },
  { href: "/risk-center", label: "Risk", icon: Shield },
] as const;

/** Operator Home — institutional morning brief from LIVE planes. */
export function OperatorHomeWorkspace() {
  const session = useTradingSession();
  const { analytics, trades } = useLiveTrades("today");
  const todayClosed = trades.filter((t) => t.status === "closed");

  const signalsQ = useQuery({
    queryKey: ["signals-center", "operator-home"],
    queryFn: () => signalCenterApi.list({}),
    staleTime: 20_000,
    refetchInterval: 40_000,
    retry: false,
  });
  const ordersQ = useQuery({
    queryKey: ["portfolio-orders", "operator-home"],
    queryFn: () => portfolioApi.orders(),
    staleTime: 12_000,
    refetchInterval: 20_000,
    retry: false,
  });
  const coachQ = useQuery({
    queryKey: ["ecosystem-coach", "operator-home"],
    queryFn: () => ecosystemApi.coach(),
    staleTime: 45_000,
    retry: false,
  });

  const dash = asRecord(asRecord(signalsQ.data).dashboard);
  const orders = asList(ordersQ.data);
  const coachRec = asList(
    asRecord(coachQ.data).recommendations ||
      asRecord(coachQ.data).advice ||
      coachQ.data,
  )
    .map(asRecord)
    .slice(0, 3);

  const floatPnl = session.positions.reduce((s, p) => s + num(asRecord(p).profit, 0), 0);

  return (
    <div className="space-y-6">
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {[
          ["Today PnL", formatNumber(analytics.todayPl, 2)],
          ["Trades", String(todayClosed.length)],
          ["Win Rate", analytics.winRate != null ? `${(analytics.winRate * 100).toFixed(1)}%` : "—"],
          ["Signals", str(dash.buy_signals || dash.total_signals, "—")],
          ["Orders", String(orders.length)],
          ["Float", formatNumber(floatPnl, 2)],
        ].map(([k, v]) => (
          <div key={k} className="border border-[var(--border)] bg-[var(--surface)] px-3 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              {k}
            </p>
            <p className="mt-1 font-mono text-[16px] text-[var(--fg)]">{v}</p>
          </div>
        ))}
      </section>

      <section className="space-y-2">
        <h2 className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Quick actions
        </h2>
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
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="border border-[var(--border)] bg-[var(--surface)]">
          <header className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
              Today&apos;s signals
            </h2>
            <Button asChild size="sm" variant="ghost">
              <Link href="/signals">Open</Link>
            </Button>
          </header>
          <ul className="divide-y divide-[var(--border)]">
            {asList(
              asRecord(signalsQ.data).items ||
                asRecord(signalsQ.data).signals ||
                signalsQ.data,
            )
              .map(asRecord)
              .slice(0, 6)
              .map((s, i) => (
                <li
                  key={`${str(s.symbol)}-${i}`}
                  className="flex items-center justify-between gap-2 px-3 py-2 text-[12px]"
                >
                  <span className="font-mono">{str(s.symbol, "—")}</span>
                  <Badge tone="neutral" className="h-5 px-1.5 text-[10px]">
                    {str(s.direction || s.side, "—")}
                  </Badge>
                  <span className="tabular text-[var(--fg-muted)]">
                    {str(s.confidence || s.quality, "—")}
                  </span>
                </li>
              ))}
            {!asList(
              asRecord(signalsQ.data).items ||
                asRecord(signalsQ.data).signals ||
                signalsQ.data,
            ).length ? (
              <li className="px-3 py-4 text-[12px] text-[var(--fg-muted)]">
                No LIVE signals in feed.
              </li>
            ) : null}
          </ul>
        </section>

        <section className="border border-[var(--border)] bg-[var(--surface)]">
          <header className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
              Today&apos;s AI advice
            </h2>
            <Button asChild size="sm" variant="ghost">
              <Link href="/ai-coach">Coach</Link>
            </Button>
          </header>
          <ul className="divide-y divide-[var(--border)]">
            {coachRec.length ? (
              coachRec.map((r, i) => (
                <li key={i} className="px-3 py-2 text-[12px] text-[var(--fg-muted)]">
                  {str(r.title || r.message || r.detail || r.reason, "—")}
                </li>
              ))
            ) : (
              <li className="px-3 py-4 text-[12px] text-[var(--fg-muted)]">
                Recommendations only — open AI Coach when feed is available.
              </li>
            )}
          </ul>
          <div className="border-t border-[var(--border)] px-3 py-2 text-[11px] text-[var(--fg-subtle)]">
            Risk plane: {session.connected ? "Broker live" : session.gatewayOnline ? "Gateway only" : "Broker off"} · Portfolio float {formatNumber(floatPnl, 2)}
          </div>
        </section>
      </div>

      <PlatformStatusBoard />
    </div>
  );
}
