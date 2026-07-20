"use client";

import { memo, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { BookOpen, History, Layers3, ListOrdered } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn, formatCurrency, formatRelativeTime } from "@/lib/utils";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { PositionManager } from "@/components/execution/position-manager";
import { OrdersWorkspace } from "@/components/execution/orders-workspace";
import { executionApi, portfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { useTradingSession } from "@/providers/trading-session-provider";
import { VirtualList } from "@/components/terminal/virtual-list";
import { TerminalEmpty } from "@/components/terminal/empty-state";
import type { TerminalBlotterTab } from "@/components/terminal/layout-store";

const TABS: {
  id: TerminalBlotterTab;
  label: string;
  icon: typeof History;
  hotkey: string;
}[] = [
  { id: "positions", label: "Positions", icon: Layers3, hotkey: "1" },
  { id: "orders", label: "Orders", icon: ListOrdered, hotkey: "2" },
  { id: "history", label: "History", icon: History, hotkey: "3" },
  { id: "journal", label: "Journal", icon: BookOpen, hotkey: "4" },
];

export const TerminalBlotter = memo(function TerminalBlotter({
  tab,
  onTabChange,
}: {
  tab: TerminalBlotterTab;
  onTabChange: (t: TerminalBlotterTab) => void;
}) {
  const session = useTradingSession();

  const historyQ = useQuery({
    queryKey: ["history"],
    queryFn: portfolioApi.history,
    retry: false,
    enabled: tab === "history" || session.connected,
    staleTime: 8_000,
  });

  const journalQ = useQuery({
    queryKey: ["execution-journal"],
    queryFn: () => executionApi.journal(100),
    retry: false,
    enabled: tab === "journal",
    staleTime: 8_000,
    refetchInterval: tab === "journal" ? 12_000 : false,
  });

  const deals = useMemo(() => {
    if (historyQ.isFetched) return asList(historyQ.data?.deals).map(asRecord);
    return session.historyDeals;
  }, [historyQ.isFetched, historyQ.data, session.historyDeals]);

  const journalRows = useMemo(
    () => asList(asRecord(journalQ.data).items).map(asRecord),
    [journalQ.data],
  );

  return (
    <section
      className="flex h-full min-h-0 flex-col bg-[var(--bg-elevated)]"
      aria-label="Blotter"
    >
      <div
        className="flex shrink-0 items-center gap-1 border-b border-[var(--border)] px-2 py-1"
        role="tablist"
        aria-label="Blotter tabs"
      >
        {TABS.map((t) => {
          const active = tab === t.id;
          const Icon = t.icon;
          return (
            <Button
              key={t.id}
              size="sm"
              variant={active ? "secondary" : "ghost"}
              className={cn("h-7 gap-1.5 px-2 text-[11px]", active && "bg-[var(--surface-2)]")}
              role="tab"
              aria-selected={active}
              onClick={() => onTabChange(t.id)}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden />
              {t.label}
              <kbd className="ml-0.5 hidden text-[9px] text-[var(--fg-subtle)] sm:inline">
                {t.hotkey}
              </kbd>
            </Button>
          );
        })}
      </div>

      <div className="min-h-0 flex-1 overflow-hidden" role="tabpanel">
        {tab === "positions" ? (
          session.connected || session.positions.length > 0 ? (
            <div className="h-full overflow-auto p-2 [&_.rounded-xl]:rounded-md [&_.shadow-sm]:shadow-none">
              <PositionManager connected={session.connected} />
            </div>
          ) : (
            <TerminalEmpty
              title="No open positions"
              description="Positions appear here when the session book is live."
              action={
                <Button size="sm" variant="secondary" asChild>
                  <Link href="/broker">Attach broker</Link>
                </Button>
              }
            />
          )
        ) : null}

        {tab === "orders" ? (
          <div className="h-full overflow-auto p-2 [&_.rounded-xl]:rounded-md [&_.shadow-sm]:shadow-none">
            <OrdersWorkspace connected={session.connected} />
          </div>
        ) : null}

        {tab === "history" ? (
          historyQ.isLoading ? (
            <DeskSkeleton />
          ) : historyQ.isError ? (
            <div className="m-3">
              <DeskError
                message="History unavailable — could not load deals from the portfolio API."
                onRetry={() => void historyQ.refetch()}
              />
            </div>
          ) : (
            <div className="flex h-full min-h-0 flex-col">
              <div className="grid shrink-0 grid-cols-[1fr_72px_72px_88px_100px] gap-2 border-b border-[var(--border)] px-3 py-1.5 text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                <span>Symbol / time</span>
                <span>Side</span>
                <span className="text-right">Vol</span>
                <span className="text-right">Price</span>
                <span className="text-right">P&L</span>
              </div>
              <VirtualList
                className="min-h-0 flex-1"
                items={deals}
                rowHeight={36}
                aria-label="Trade history"
                empty={
                  <TerminalEmpty
                    title="No completed trades"
                    description="Filled deals from the live book will list here."
                  />
                }
                renderRow={(d) => {
                  const pnl = num(d.profit);
                  return (
                    <div className="grid h-9 grid-cols-[1fr_72px_72px_88px_100px] items-center gap-2 border-b border-[var(--border)] px-3 text-[11px]">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-[var(--fg)]">
                          {str(d.symbol, "—")}
                        </p>
                        <p className="truncate text-[10px] text-[var(--fg-subtle)]">
                          {d.time
                            ? formatRelativeTime(
                                new Date(String(d.time)).toISOString(),
                              )
                            : "—"}
                        </p>
                      </div>
                      <span className="uppercase text-[var(--fg-muted)]">
                        {str(d.side, "—")}
                      </span>
                      <span className="text-right tabular">{str(d.volume, "—")}</span>
                      <span className="text-right tabular">{str(d.price, "—")}</span>
                      <span
                        className={cn(
                          "text-right tabular",
                          Number.isFinite(pnl) && pnl >= 0
                            ? "text-[var(--success)]"
                            : Number.isFinite(pnl)
                              ? "text-[var(--danger)]"
                              : "text-[var(--fg-muted)]",
                        )}
                      >
                        {Number.isFinite(pnl) ? formatCurrency(pnl) : "—"}
                      </span>
                    </div>
                  );
                }}
              />
            </div>
          )
        ) : null}

        {tab === "journal" ? (
          journalQ.isLoading ? (
            <DeskSkeleton />
          ) : journalQ.isError ? (
            <div className="m-3">
              <DeskError
                message="Journal unavailable — execution journal could not be loaded."
                onRetry={() => void journalQ.refetch()}
              />
            </div>
          ) : journalRows.length === 0 ? (
            <TerminalEmpty
              title="No journal entries"
              description="Pre-trade and execution events appear after live activity."
            />
          ) : (
            <VirtualList
              className="min-h-0 flex-1"
              items={journalRows}
              rowHeight={40}
              aria-label="Execution journal"
              renderRow={(row) => (
                <div className="flex h-10 items-center justify-between gap-3 border-b border-[var(--border)] px-3 text-[11px]">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-[var(--fg)]">
                      {str(row.action ?? row.event ?? row.type, "Event")}
                    </p>
                    <p className="truncate text-[10px] text-[var(--fg-subtle)]">
                      {str(row.symbol, "")} {str(row.message ?? row.detail, "")}
                    </p>
                  </div>
                  <span className="shrink-0 tabular text-[var(--fg-subtle)]">
                    {row.created_at || row.time
                      ? formatRelativeTime(
                          new Date(
                            String(row.created_at ?? row.time),
                          ).toISOString(),
                        )
                      : "—"}
                  </span>
                </div>
              )}
            />
          )
        ) : null}
      </div>
    </section>
  );
});
