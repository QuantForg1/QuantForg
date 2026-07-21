"use client";

import { memo } from "react";
import Link from "next/link";
import { Layers3, ListOrdered } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { PositionManager } from "@/components/execution/position-manager";
import { OrdersWorkspace } from "@/components/execution/orders-workspace";
import { useTradingSession } from "@/providers/trading-session-provider";
import { TerminalEmpty } from "@/components/terminal/empty-state";
import type { TerminalBlotterTab } from "@/components/terminal/layout-store";

const TABS: {
  id: TerminalBlotterTab;
  label: string;
  icon: typeof Layers3;
  hotkey: string;
}[] = [
  { id: "positions", label: "Positions", icon: Layers3, hotkey: "1" },
  { id: "orders", label: "Orders", icon: ListOrdered, hotkey: "2" },
];

/**
 * Trading blotter only — history / journal / analytics live on dedicated pages.
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

  return (
    <section
      className="flex h-full min-h-0 flex-col bg-[var(--bg-elevated)]"
      aria-label="Position manager"
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
        <div className="flex items-center gap-2 pr-1 text-[10px]">
          <Link href="/journal" className="text-[var(--fg-muted)] hover:text-[var(--fg)]">
            Journal
          </Link>
          <Link
            href="/analytics"
            className="text-[var(--fg-muted)] hover:text-[var(--fg)]"
          >
            Analytics
          </Link>
        </div>
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
              description="Open positions and position manager appear when the book is live."
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
      </div>
    </section>
  );
});
