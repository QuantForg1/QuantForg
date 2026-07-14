"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { ConnectionBar } from "@/components/execution/connection-bar";
import { MarketWatch } from "@/components/execution/market-watch";
import { ExecutionOrderTicket } from "@/components/execution/order-ticket";
import { PositionManager } from "@/components/execution/position-manager";
import { OrdersWorkspace } from "@/components/execution/orders-workspace";
import { PageMotion } from "@/components/desk/motion";
import { DeskEmpty, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { RealtimeConnectionBadge, RealtimeMeta } from "@/components/realtime/connection-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SessionStrip } from "@/components/broker/session-strip";
import { useExecutionStream } from "@/hooks/realtime";
import { useTradingSession } from "@/providers/trading-session-provider";
import { mt5Api } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { classifySymbol } from "@/lib/dashboard/derive";
import { Cable, History, Layers3, ListOrdered, NotebookPen, Shield } from "lucide-react";

const TABS = [
  { id: "positions", label: "Positions", icon: Layers3 },
  { id: "orders", label: "Orders", icon: ListOrdered },
  { id: "history", label: "History", icon: History },
  { id: "exposure", label: "Exposure", icon: Shield },
  { id: "risk", label: "Risk", icon: Shield },
  { id: "journal", label: "Journal", icon: NotebookPen },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function ExecutionPage() {
  const [symbol, setSymbol] = useState("EURUSD");
  const [tab, setTab] = useState<TabId>("positions");
  const session = useTradingSession();
  const realtime = useExecutionStream(symbol);
  const connected = session.connected;

  const symbolsQ = useQuery({
    queryKey: ["mt5-symbols", "", 0],
    queryFn: () => mt5Api.symbols({ limit: 100, offset: 0, include_quotes: false }),
    retry: false,
    enabled: connected,
    staleTime: 45_000,
  });

  const tickQ = useQuery({
    queryKey: ["mt5-tick", symbol],
    queryFn: () => mt5Api.tick(symbol),
    retry: false,
    enabled: connected && Boolean(symbol),
  });

  const tick = asRecord(tickQ.data);
  const fromSymbols = useMemo(() => {
    const hit = asList(symbolsQ.data)
      .map(asRecord)
      .find((s) => str(s.code) === symbol);
    return hit ?? {};
  }, [symbolsQ.data, symbol]);

  const bid = num(tick.bid, num(fromSymbols.bid));
  const ask = num(tick.ask, num(fromSymbols.ask));

  const exposure = useMemo(() => {
    const map = new Map<string, number>();
    for (const p of session.positions) {
      const cls = classifySymbol(str(p.symbol));
      const notional = Math.abs(num(p.volume, 0) * num(p.current_price ?? p.open_price, 0));
      map.set(cls, (map.get(cls) ?? 0) + notional);
    }
    return [...map.entries()].sort((a, b) => b[1] - a[1]);
  }, [session.positions]);

  return (
    <div>
      <PageHeader
        title="Trading Terminal"
        description="Institutional execution desk — market watch, ticket, and synchronized book from the live MT5 session."
        actions={<RealtimeConnectionBadge status={realtime} />}
      />
      <RealtimeMeta status={realtime} className="mb-3" />
      <SessionStrip className="mb-4" />

      {session.refreshing && !session.login && !connected ? (
        <DeskSkeleton variant="page" />
      ) : (
        <PageMotion className="space-y-4">
          <ConnectionBar
            connected={connected}
            server={session.server}
            login={session.login}
            latencyMs={realtime.latencyMs ?? session.latencyMs}
            tradingEnabled={connected}
          />

          <div className="grid gap-4 xl:grid-cols-[0.95fr_1.15fr]">
            <MarketWatch
              connected={connected}
              selected={symbol}
              onSelect={setSymbol}
              latencyMs={session.latencyMs}
            />
            <ExecutionOrderTicket
              symbol={symbol}
              onSymbolChange={setSymbol}
              connected={connected}
              bid={Number.isFinite(bid) ? bid : undefined}
              ask={Number.isFinite(ask) ? ask : undefined}
            />
          </div>

          <Card>
            <CardHeader className="space-y-3">
              <CardTitle>Book</CardTitle>
              <div className="flex flex-wrap gap-1" role="tablist" aria-label="Terminal book">
                {TABS.map((t) => {
                  const Icon = t.icon;
                  return (
                    <Button
                      key={t.id}
                      size="sm"
                      role="tab"
                      aria-selected={tab === t.id}
                      variant={tab === t.id ? "default" : "ghost"}
                      className="h-8 gap-1.5"
                      onClick={() => setTab(t.id)}
                    >
                      <Icon className="h-3.5 w-3.5" />
                      {t.label}
                    </Button>
                  );
                })}
              </div>
            </CardHeader>
            <CardContent>
              {!connected ? (
                <DeskEmpty
                  icon={Cable}
                  title="Session offline"
                  description="Attach the broker session to sync positions, orders, and history."
                  actionLabel="Broker Workspace"
                  onAction={() => {
                    window.location.href = "/broker";
                  }}
                />
              ) : tab === "positions" ? (
                <PositionManager connected={connected} />
              ) : tab === "orders" ? (
                <OrdersWorkspace connected={connected} />
              ) : tab === "history" ? (
                session.historyDeals.length === 0 ? (
                  <p className="py-6 text-center text-sm text-[var(--fg-muted)]">
                    No recent deals synced.
                  </p>
                ) : (
                  <DeskTable
                    columns={["Symbol", "Volume", "Profit", "Time"]}
                    rows={session.historyDeals.slice(0, 40).map((d) => [
                      str(d.symbol),
                      str(d.volume),
                      str(d.profit),
                      str(d.time, "—").replace("T", " ").slice(0, 19),
                    ])}
                  />
                )
              ) : tab === "exposure" ? (
                exposure.length === 0 ? (
                  <p className="py-6 text-center text-sm text-[var(--fg-muted)]">
                    No exposure while flat.
                  </p>
                ) : (
                  <DeskTable
                    columns={["Class", "Notional"]}
                    rows={exposure.map(([k, v]) => [k, v.toFixed(2)])}
                  />
                )
              ) : tab === "risk" ? (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {[
                    ["Margin", session.margin],
                    ["Free margin", session.freeMargin],
                    ["Margin level", session.marginLevel],
                    ["Floating P/L", session.profit],
                  ].map(([label, value]) => (
                    <div
                      key={label}
                      className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/80 px-3 py-3"
                    >
                      <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                        {label}
                      </p>
                      <p className="mt-1 font-mono text-sm tabular">{value}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="py-6 text-sm text-[var(--fg-muted)]">
                  Journal entries sync from executed deals in Trade History. Use the History tab for
                  the live ticket tape from the attached session.
                </p>
              )}
            </CardContent>
          </Card>
        </PageMotion>
      )}
    </div>
  );
}
