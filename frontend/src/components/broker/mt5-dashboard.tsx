"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { StatCard } from "@/components/dashboard/stat-card";
import { DeskTable } from "@/components/desk/primitives";
import { Badge } from "@/components/ui/badge";
import { useBookStream, useMarketStream } from "@/hooks/realtime";
import { mt5Api } from "@/lib/api/endpoints";
import { computeDealStats } from "@/lib/dashboard/deal-stats";
import { asRecord, num, str, toneFromNumber } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { useTradingSession } from "@/providers/trading-session-provider";
import { formatCurrency, formatNumber } from "@/lib/utils";

function money(v: number): string {
  if (!Number.isFinite(v)) return "—";
  return formatCurrency(v);
}

function pct(v: number, digits = 1): string {
  if (!Number.isFinite(v)) return "—";
  return `${formatNumber(v * (v <= 1 ? 100 : 1), digits)}%`;
}

function ratio(v: number, digits = 2): string {
  if (!Number.isFinite(v)) return "—";
  return formatNumber(v, digits);
}

/**
 * Live MT5 Broker Dashboard — account, risk, performance, quotes, and book.
 * Every field is from MT5 sync / ticks / deal history. Empty → "—".
 */
export function Mt5BrokerDashboard() {
  const session = useTradingSession();
  useBookStream(session.connected);
  useMarketStream(TRADING_SYMBOL, session.connected);

  const tickQ = useQuery({
    queryKey: ["mt5-tick", TRADING_SYMBOL],
    queryFn: () => mt5Api.tick(TRADING_SYMBOL),
    enabled: session.connected,
    staleTime: 2_000,
    refetchInterval: session.connected ? 3_000 : false,
    retry: false,
  });

  const tick = asRecord(tickQ.data);
  const bid = num(tick.bid);
  const ask = num(tick.ask);
  const spread =
    Number.isFinite(bid) && Number.isFinite(ask) ? ask - bid : NaN;

  const floating = num(session.profit);
  const equity = num(session.equity);
  const balance = num(session.balance);
  const freeMargin = num(session.freeMargin);
  const marginLevel = num(session.marginLevel);

  const deals = session.historyDeals;
  const positions = session.positions;
  const orders = session.orders;

  const stats = useMemo(
    () =>
      computeDealStats(deals, {
        floatingProfit: Number.isFinite(floating) ? floating : 0,
        equity: Number.isFinite(equity) ? equity : undefined,
      }),
    [deals, floating, equity],
  );

  const recent = deals.slice(0, 15);
  const history = deals.slice(0, 40);

  if (!session.connected) {
    return (
      <section
        id="bw-dashboard"
        className="scroll-mt-24 rounded-2xl border border-[var(--border)] bg-[var(--surface)]/90 p-5 shadow-[var(--shadow-card)]"
        aria-label="MT5 Broker Dashboard"
      >
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-medium tracking-wide text-[var(--fg)]">
            MT5 Broker Dashboard
          </h2>
          <Badge tone="warning">Session offline</Badge>
        </div>
        <p className="text-sm text-[var(--fg-muted)]">
          Attach the live MT5 session to populate balance, equity, positions, and
          trade statistics. QuantForg never invents account figures.
        </p>
      </section>
    );
  }

  return (
    <section
      id="bw-dashboard"
      className="scroll-mt-24 space-y-5 rounded-2xl border border-[var(--border)] bg-[var(--surface)]/90 p-5 shadow-[var(--shadow-card)]"
      aria-label="MT5 Broker Dashboard"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-medium tracking-wide text-[var(--fg)]">
            MT5 Broker Dashboard
          </h2>
          <p className="mt-0.5 text-xs text-[var(--fg-subtle)]">
            Live book · {session.login} · {session.server}
            {session.refreshing ? " · syncing…" : ""}
          </p>
        </div>
        <Badge tone="success">Live</Badge>
      </div>

      {/* Account */}
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Account
        </p>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
          <StatCard label="Balance" value={money(balance)} />
          <StatCard
            label="Equity"
            value={money(equity)}
            tone={toneFromNumber(equity - balance)}
          />
          <StatCard label="Free Margin" value={money(freeMargin)} />
          <StatCard
            label="Margin Level"
            value={
              Number.isFinite(marginLevel)
                ? `${formatNumber(marginLevel, 1)}%`
                : "—"
            }
          />
          <StatCard
            label="Floating Profit"
            value={money(floating)}
            tone={toneFromNumber(floating)}
          />
          <StatCard
            label="Today's Profit"
            value={money(stats.todayProfit)}
            tone={toneFromNumber(stats.todayProfit)}
            hint={
              Number.isFinite(stats.todayRealized)
                ? `Realized ${money(stats.todayRealized)} + floating`
                : undefined
            }
          />
        </div>
      </div>

      {/* Performance from deals */}
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Performance · closed deals
        </p>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
          <StatCard
            label="Win Rate"
            value={pct(stats.winRate)}
            hint={stats.tradeCount ? `${stats.tradeCount} trades` : "No closed trades"}
          />
          <StatCard label="Profit Factor" value={ratio(stats.profitFactor)} />
          <StatCard
            label="Average Win"
            value={money(stats.averageWin)}
            tone="up"
          />
          <StatCard
            label="Average Loss"
            value={money(stats.averageLoss)}
            tone="down"
          />
          <StatCard
            label="Daily Drawdown"
            value={
              Number.isFinite(stats.dailyDrawdown)
                ? money(stats.dailyDrawdown)
                : "—"
            }
            tone={
              Number.isFinite(stats.dailyDrawdown) && stats.dailyDrawdown > 0
                ? "down"
                : "neutral"
            }
            hint={
              Number.isFinite(stats.dailyDrawdownPct)
                ? `${formatNumber(stats.dailyDrawdownPct, 2)}% of equity`
                : undefined
            }
          />
        </div>
      </div>

      {/* Quotes */}
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Market · {TRADING_SYMBOL}
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard
            label="Current Bid"
            value={Number.isFinite(bid) ? formatNumber(bid, 2) : "—"}
            tone="down"
          />
          <StatCard
            label="Current Ask"
            value={Number.isFinite(ask) ? formatNumber(ask, 2) : "—"}
            tone="up"
          />
          <StatCard
            label="Current Spread"
            value={Number.isFinite(spread) ? formatNumber(spread, 2) : "—"}
          />
        </div>
      </div>

      {/* Book tables */}
      <div className="grid gap-4 xl:grid-cols-2">
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Open Positions · {positions.length}
          </p>
          {positions.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No open positions</p>
          ) : (
            <DeskTable
              columns={["Symbol", "Side", "Vol", "Open", "SL", "TP", "P/L"]}
              rows={positions.slice(0, 25).map((p) => [
                str(p.symbol),
                str(p.side),
                str(p.volume),
                str(p.open_price ?? p.price_open),
                str(p.stop_loss ?? p.sl, "—"),
                str(p.take_profit ?? p.tp, "—"),
                str(p.profit),
              ])}
            />
          )}
        </div>
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Pending Orders · {orders.length}
          </p>
          {orders.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No pending orders</p>
          ) : (
            <DeskTable
              columns={["Symbol", "Type", "Vol", "Price", "SL", "TP"]}
              rows={orders.slice(0, 25).map((o) => [
                str(o.symbol),
                str(o.order_type || o.type),
                str(o.volume ?? o.volume_current),
                str(o.price ?? o.price_open),
                str(o.stop_loss ?? o.sl, "—"),
                str(o.take_profit ?? o.tp, "—"),
              ])}
            />
          )}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Recent Trades
          </p>
          {recent.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No completed trades</p>
          ) : (
            <DeskTable
              columns={["Symbol", "Side", "Vol", "Price", "Profit", "Time"]}
              rows={recent.map((d) => [
                str(d.symbol),
                str(d.side || d.deal_type, "—"),
                str(d.volume),
                str(d.price, "—"),
                str(d.profit),
                str(d.time, "—").replace("T", " ").slice(0, 19),
              ])}
            />
          )}
        </div>
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Trade History
          </p>
          {history.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No completed trades</p>
          ) : (
            <DeskTable
              columns={["Ticket", "Symbol", "Vol", "Profit", "Time"]}
              rows={history.map((d) => [
                str(d.ticket),
                str(d.symbol),
                str(d.volume),
                str(d.profit),
                str(d.time, "—").replace("T", " ").slice(0, 19),
              ])}
            />
          )}
        </div>
      </div>
    </section>
  );
}
