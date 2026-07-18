"use client";

import { memo } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ExecutionOrderTicket,
  type OrderTicketHandle,
} from "@/components/execution/order-ticket";
import { useTradingSession } from "@/providers/trading-session-provider";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { num } from "@/lib/desk";
import type { RefObject } from "react";
import { ExecutionReadiness } from "@/components/os/execution-readiness";

export const WorkspaceRightRail = memo(function WorkspaceRightRail({
  symbol,
  onSymbolChange,
  connected,
  bid,
  ask,
  ticketRef,
}: {
  symbol: string;
  onSymbolChange: (s: string) => void;
  connected: boolean;
  bid?: number;
  ask?: number;
  ticketRef: RefObject<OrderTicketHandle | null>;
}) {
  const session = useTradingSession();
  const equity = num(session.equity);
  const balance = num(session.balance);
  const margin = num(session.margin);
  const free = num(session.freeMargin);
  const profit = num(session.profit);
  const marginLevel = num(session.marginLevel);
  const openPnl = session.positions.reduce((s, p) => s + num(p.profit, 0), 0);
  const hasQuote =
    typeof bid === "number" &&
    typeof ask === "number" &&
    Number.isFinite(bid) &&
    Number.isFinite(ask);

  return (
    <aside
      className="flex h-full min-h-0 flex-col border-l border-[var(--border)] bg-[var(--bg-elevated)]"
      aria-label="Order & risk rail"
    >
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="border-b border-[var(--border)]">
          <ExecutionOrderTicket
            ref={ticketRef}
            symbol={symbol}
            onSymbolChange={onSymbolChange}
            connected={connected}
            bid={bid}
            ask={ask}
            dense
          />
        </div>

        <div className="border-b border-[var(--border)] p-3">
          <ExecutionReadiness
            checks={[
              {
                id: "session",
                label: "Session attached",
                ok: session.connected,
              },
              {
                id: "quote",
                label: "Live quote",
                ok: connected ? hasQuote : null,
              },
              {
                id: "margin",
                label: "Free margin",
                ok: session.connected
                  ? Number.isFinite(free) && free > 0
                  : null,
              },
              {
                id: "level",
                label: "Margin level",
                ok: session.connected
                  ? !Number.isFinite(marginLevel) || marginLevel === 0 || marginLevel >= 100
                  : null,
                detail: Number.isFinite(marginLevel) ? `${marginLevel}` : undefined,
              },
            ]}
          />
        </div>

        <section className="border-b border-[var(--border)] p-3" aria-label="Account">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="qf-label text-[var(--fg-subtle)]">Account</h2>
            <Badge tone={session.connected ? "success" : "warning"} className="text-[10px]">
              {session.loginStatus}
            </Badge>
          </div>
          <dl className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <dt className="text-[var(--fg-subtle)]">Broker</dt>
              <dd className="truncate font-medium">{session.server}</dd>
            </div>
            <div>
              <dt className="text-[var(--fg-subtle)]">Login</dt>
              <dd className="tabular font-medium">{session.login}</dd>
            </div>
            <div>
              <dt className="text-[var(--fg-subtle)]">Balance</dt>
              <dd className="tabular font-medium">
                {Number.isFinite(balance) ? formatCurrency(balance) : session.balance}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--fg-subtle)]">Equity</dt>
              <dd className="tabular font-medium">
                {Number.isFinite(equity) ? formatCurrency(equity) : session.equity}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--fg-subtle)]">Margin</dt>
              <dd className="tabular font-medium">
                {Number.isFinite(margin) ? formatCurrency(margin) : session.margin}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--fg-subtle)]">Free margin</dt>
              <dd className="tabular font-medium">
                {Number.isFinite(free) ? formatCurrency(free) : session.freeMargin}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--fg-subtle)]">Leverage</dt>
              <dd className="tabular font-medium">{session.leverage}</dd>
            </div>
            <div>
              <dt className="text-[var(--fg-subtle)]">Margin level</dt>
              <dd className="tabular font-medium">
                {Number.isFinite(marginLevel) ? formatNumber(marginLevel, 2) : session.marginLevel}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--fg-subtle)]">Floating</dt>
              <dd
                className={`tabular font-medium ${
                  openPnl >= 0 || profit >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"
                }`}
              >
                {Number.isFinite(openPnl)
                  ? formatCurrency(openPnl)
                  : Number.isFinite(profit)
                    ? formatCurrency(profit)
                    : session.profit}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--fg-subtle)]">Positions</dt>
              <dd className="tabular font-medium">{session.positions.length}</dd>
            </div>
          </dl>
          <Button size="sm" variant="ghost" className="mt-2 h-7 px-2 text-[10px]" asChild>
            <Link href="/book">Open Book</Link>
          </Button>
        </section>
      </div>
    </aside>
  );
});
