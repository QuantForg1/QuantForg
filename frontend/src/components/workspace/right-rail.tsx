"use client";

import { memo, useMemo } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ExecutionOrderTicket,
  type OrderTicketHandle,
} from "@/components/execution/order-ticket";
import { portfolioApi, mt5Api } from "@/lib/api/endpoints";
import { asList, asRecord, metric, num, str } from "@/lib/desk";
import { formatCurrency, formatNumber } from "@/lib/utils";
import type { RefObject } from "react";

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
  const positionsQ = useQuery({
    queryKey: ["positions"],
    queryFn: () => portfolioApi.positions(),
    retry: false,
  });
  const ordersQ = useQuery({
    queryKey: ["orders"],
    queryFn: portfolioApi.orders,
    retry: false,
  });
  const portfolioQ = useQuery({
    queryKey: ["portfolio"],
    queryFn: portfolioApi.get,
    retry: false,
  });
  const accountQ = useQuery({
    queryKey: ["mt5-account"],
    queryFn: mt5Api.account,
    retry: false,
    enabled: connected,
  });

  const positions = useMemo(() => asList(positionsQ.data).map(asRecord), [positionsQ.data]);
  const orders = useMemo(() => asList(ordersQ.data).map(asRecord), [ordersQ.data]);
  const account = asRecord(portfolioQ.data?.account ?? accountQ.data);
  const equity = metric(account, "equity");
  const balance = metric(account, "balance");
  const margin = metric(account, "margin");
  const free = metric(account, "free_margin", "margin_free");
  const profit = metric(account, "profit");
  const marginLevel = metric(account, "margin_level");

  const openPnl = positions.reduce((s, p) => s + num(p.profit, 0), 0);

  return (
    <aside
      className="flex h-full min-h-0 flex-col border-l border-[var(--border)] bg-[var(--bg-elevated)]/40"
      aria-label="Trading sidebar"
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

        <section className="border-b border-[var(--border)] p-3" aria-label="Risk summary">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Risk summary
            </h2>
            <Button size="sm" variant="ghost" className="h-6 px-2 text-[10px]" asChild>
              <Link href="/risk">Full risk</Link>
            </Button>
          </div>
          <dl className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <dt className="text-[var(--fg-subtle)]">Equity</dt>
              <dd className="tabular font-medium">
                {Number.isFinite(equity) ? formatCurrency(equity) : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--fg-subtle)]">Balance</dt>
              <dd className="tabular font-medium">
                {Number.isFinite(balance) ? formatCurrency(balance) : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--fg-subtle)]">Margin</dt>
              <dd className="tabular font-medium">
                {Number.isFinite(margin) ? formatCurrency(margin) : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--fg-subtle)]">Free margin</dt>
              <dd className="tabular font-medium">
                {Number.isFinite(free) ? formatCurrency(free) : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--fg-subtle)]">Floating</dt>
              <dd
                className={`tabular font-medium ${
                  openPnl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"
                }`}
              >
                {formatCurrency(Number.isFinite(profit) ? profit : openPnl)}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--fg-subtle)]">Margin level</dt>
              <dd className="tabular font-medium">
                {Number.isFinite(marginLevel) ? `${formatNumber(marginLevel, 1)}%` : "—"}
              </dd>
            </div>
          </dl>
        </section>

        <section className="border-b border-[var(--border)] p-3" aria-label="Open positions">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Open positions
            </h2>
            <Badge tone="neutral">{positions.length}</Badge>
          </div>
          {positions.length === 0 ? (
            <p className="text-xs text-[var(--fg-muted)]">No open positions.</p>
          ) : (
            <ul className="max-h-40 space-y-1 overflow-y-auto">
              {positions.slice(0, 50).map((p) => {
                const pnl = num(p.profit, 0);
                return (
                  <li
                    key={str(p.ticket, str(p.symbol))}
                    className="flex items-center justify-between rounded-md bg-[var(--surface)] px-2 py-1.5 text-[11px]"
                  >
                    <button
                      type="button"
                      className="text-left font-medium hover:text-[var(--accent)]"
                      onClick={() => onSymbolChange(str(p.symbol))}
                    >
                      {str(p.symbol)}{" "}
                      <span className="text-[var(--fg-subtle)]">{str(p.side)}</span>
                    </button>
                    <span className={pnl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}>
                      {formatCurrency(pnl)}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="border-b border-[var(--border)] p-3" aria-label="Pending orders">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Pending orders
            </h2>
            <Badge tone="neutral">{orders.length}</Badge>
          </div>
          {orders.length === 0 ? (
            <p className="text-xs text-[var(--fg-muted)]">No pending orders.</p>
          ) : (
            <ul className="max-h-36 space-y-1 overflow-y-auto">
              {orders.slice(0, 50).map((o) => (
                <li
                  key={str(o.ticket, `${str(o.symbol)}-${str(o.price)}`)}
                  className="flex items-center justify-between rounded-md bg-[var(--surface)] px-2 py-1.5 text-[11px]"
                >
                  <button
                    type="button"
                    className="text-left font-medium hover:text-[var(--accent)]"
                    onClick={() => onSymbolChange(str(o.symbol))}
                  >
                    {str(o.symbol)} · {str(o.order_type, str(o.type))}
                  </button>
                  <span className="tabular text-[var(--fg-muted)]">{str(o.volume)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="p-3" aria-label="Quick actions">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Quick actions
          </h2>
          <div className="grid grid-cols-2 gap-1.5">
            <Button
              size="sm"
              className="h-8 text-xs"
              disabled={!connected}
              onClick={() => ticketRef.current?.buy()}
            >
              Buy (B)
            </Button>
            <Button
              size="sm"
              variant="danger"
              className="h-8 text-xs"
              disabled={!connected}
              onClick={() => ticketRef.current?.sell()}
            >
              Sell (S)
            </Button>
            <Button size="sm" variant="secondary" className="h-8 text-xs" asChild>
              <Link href="/execution">Execution</Link>
            </Button>
            <Button size="sm" variant="secondary" className="h-8 text-xs" asChild>
              <Link href="/positions">Positions</Link>
            </Button>
            <Button size="sm" variant="ghost" className="h-8 text-xs col-span-2" asChild>
              <Link href="/history">Trade history</Link>
            </Button>
          </div>
        </section>
      </div>
    </aside>
  );
});
