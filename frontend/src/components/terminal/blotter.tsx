"use client";

import { memo } from "react";
import Link from "next/link";
import { History, Layers3, ListOrdered } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn, formatCurrency, formatNumber } from "@/lib/utils";
import { PositionManager } from "@/components/execution/position-manager";
import { OrdersWorkspace } from "@/components/execution/orders-workspace";
import { useTradingSession } from "@/providers/trading-session-provider";
import { TerminalEmpty } from "@/components/terminal/empty-state";
import type { TerminalBlotterTab } from "@/components/terminal/layout-store";
import { asRecord, num, str } from "@/lib/desk";

const TABS: {
  id: TerminalBlotterTab;
  label: string;
  icon: typeof Layers3;
  hotkey: string;
}[] = [
  { id: "positions", label: "Positions", icon: Layers3, hotkey: "1" },
  { id: "orders", label: "Orders", icon: ListOrdered, hotkey: "2" },
  { id: "executions", label: "Executions", icon: History, hotkey: "3" },
];

/**
 * Trading blotter — Positions · Orders · Executions only.
 * Analytics / journal live on dedicated History workspace pages.
 */
export const TerminalBlotter = memo(function TerminalBlotter({
  tab,
  onTabChange,
}: {
  tab: TerminalBlotterTab;
  onTabChange: (t: TerminalBlotterTab) => void;
}) {
  const session = useTradingSession();
  const openCount = session.positions.length;
  const deals = session.historyDeals;

  return (
    <section
      className="flex h-full min-h-0 flex-col bg-[var(--bg-elevated)]"
      aria-label="Trading blotter"
    >
      <div
        className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--border)] px-2 py-1"
        role="tablist"
        aria-label="Blotter tabs"
      >
        <div className="flex items-center gap-1">
          {TABS.map((t) => {
            const active = tab === t.id;
            const Icon = t.icon;
            return (
              <Button
                key={t.id}
                size="sm"
                variant={active ? "secondary" : "ghost"}
                className={cn(
                  "h-7 gap-1.5 px-2 text-[11px]",
                  active && "bg-[var(--surface-2)]",
                )}
                role="tab"
                aria-selected={active}
                onClick={() => onTabChange(t.id)}
              >
                <Icon className="h-3.5 w-3.5" aria-hidden />
                {t.label}
                {t.id === "positions" && openCount > 0 ? (
                  <span className="ml-0.5 tabular text-[var(--fg-subtle)]">
                    {openCount}
                  </span>
                ) : null}
                <kbd className="ml-0.5 hidden text-[9px] text-[var(--fg-subtle)] sm:inline">
                  {t.hotkey}
                </kbd>
              </Button>
            );
          })}
        </div>
        <Link
          href="/journal"
          className="pr-1 text-[10px] text-[var(--fg-muted)] hover:text-[var(--fg)]"
        >
          Journal →
        </Link>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden" role="tabpanel">
        {tab === "positions" ? (
          session.connected || openCount > 0 ? (
            <div className="h-full overflow-auto p-1 [&_.rounded-xl]:rounded-md [&_.shadow-sm]:shadow-none">
              <PositionManager connected={session.connected} />
            </div>
          ) : (
            <TerminalEmpty
              title="No open positions"
              description="Open positions appear when the live book is attached."
              action={
                <Button size="sm" variant="secondary" asChild>
                  <Link href="/broker">Attach broker</Link>
                </Button>
              }
            />
          )
        ) : null}

        {tab === "orders" ? (
          <div className="h-full overflow-auto p-1 [&_.rounded-xl]:rounded-md [&_.shadow-sm]:shadow-none">
            <OrdersWorkspace connected={session.connected} />
          </div>
        ) : null}

        {tab === "executions" ? (
          deals.length === 0 ? (
            <TerminalEmpty
              title="No executions yet"
              description="Closed deals from the MT5 session appear here after sync."
              action={
                <Button size="sm" variant="secondary" asChild>
                  <Link href="/executions">Open executions desk</Link>
                </Button>
              }
            />
          ) : (
            <div className="h-full overflow-auto">
              <table className="w-full text-left text-[11px]">
                <thead className="sticky top-0 bg-[var(--bg-elevated)] text-[var(--fg-subtle)]">
                  <tr className="border-b border-[var(--border)]">
                    <th className="px-2 py-1.5 font-medium">Time</th>
                    <th className="px-2 py-1.5 font-medium">Symbol</th>
                    <th className="px-2 py-1.5 font-medium">Side</th>
                    <th className="px-2 py-1.5 font-medium">Vol</th>
                    <th className="px-2 py-1.5 font-medium">Price</th>
                    <th className="px-2 py-1.5 font-medium">PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {deals.slice(0, 80).map((raw, i) => {
                    const d = asRecord(raw);
                    const pnl = num(d.profit, 0);
                    return (
                      <tr
                        key={str(d.ticket ?? d.deal ?? i)}
                        className="border-b border-[var(--border)]/60 hover:bg-[var(--surface-2)]"
                      >
                        <td className="px-2 py-1 tabular text-[var(--fg-muted)]">
                          {str(d.time ?? d.closed_at, "—")}
                        </td>
                        <td className="px-2 py-1 font-medium">{str(d.symbol)}</td>
                        <td className="px-2 py-1 uppercase">{str(d.side ?? d.type)}</td>
                        <td className="px-2 py-1 tabular">
                          {formatNumber(num(d.volume ?? d.lots, 0), 2)}
                        </td>
                        <td className="px-2 py-1 tabular">
                          {formatNumber(num(d.price, 0), 2)}
                        </td>
                        <td
                          className={cn(
                            "px-2 py-1 tabular",
                            pnl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
                          )}
                        >
                          {formatCurrency(pnl)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )
        ) : null}
      </div>
    </section>
  );
});
