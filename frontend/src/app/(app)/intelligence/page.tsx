"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { PageMotion } from "@/components/desk/motion";
import { intelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";
import { Newspaper, Radio } from "lucide-react";

export default function MarketIntelligencePage() {
  const dash = useQuery({
    queryKey: ["intelligence-dashboard"],
    queryFn: () => intelligenceApi.dashboard("FX"),
    retry: false,
    refetchInterval: 30_000,
  });

  if (dash.isLoading) return <DeskSkeleton variant="page" />;
  if (dash.isError) {
    return (
      <div>
        <PageHeader
          title="Market Intelligence"
          description="Live MT5 sync, session context, configured news, and advisory analysis."
        />
        <DeskError message="Unable to load intelligence dashboard." onRetry={() => dash.refetch()} />
      </div>
    );
  }

  const data = asRecord(dash.data);
  const broker = asRecord(data.broker);
  const account = asRecord(data.account);
  const context = asRecord(data.market_context);
  const market = asRecord(data.market);
  const analysis = asRecord(data.analysis);
  const providers = asRecord(data.providers);
  const positions = asList(data.positions).map(asRecord);
  const pending = asList(data.pending_orders).map(asRecord);
  const news = asList(data.news).map(asRecord);
  const events = asList(data.economic_events).map(asRecord);
  const spreads = asList(market.spread_movers).map(asRecord);
  const history = asRecord(data.history);

  return (
    <div>
      <PageHeader
        title="Market Intelligence"
        description="Real broker sync and market context. News only from configured licensed feeds — never invented."
      />
      <PageMotion>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-8">
          <StatCard
            label="Broker"
            value={broker.connected ? "connected" : "disconnected"}
            hint={str(broker.server || broker.status)}
          />
          <StatCard label="Balance" value={str(account.balance, "—")} hint={str(account.currency, "")} />
          <StatCard label="Equity" value={str(account.equity, "—")} />
          <StatCard label="Margin" value={str(account.margin, "—")} hint={`Free ${str(account.free_margin, "—")}`} />
          <StatCard label="Session" value={str(context.session, "—")} hint={str(context.market_state)} />
          <StatCard label="Volatility" value={str(context.volatility_level, "—")} hint={str(context.liquidity_level)} />
          <StatCard
            label="Latency"
            value={
              Number.isFinite(num(broker.latency_ms))
                ? `${formatNumber(num(broker.latency_ms), 0)} ms`
                : "—"
            }
          />
          <StatCard
            label="History"
            value={`${str(history.deals_count, "0")} deals`}
            hint={`${str(history.orders_count, "0")} orders`}
          />
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Market status</CardTitle>
              <Badge tone={broker.connected ? "success" : "warning"}>
                {str(broker.login_status, broker.connected ? "live" : "offline")}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-[var(--fg-muted)]">
              <p>
                Day type · <span className="text-[var(--fg)]">{str(context.day_type, "—")}</span>
              </p>
              <p>
                Local · <span className="text-[var(--fg)]">{str(context.local_time).slice(0, 19)}</span>
              </p>
              <p>
                Quotes sampled ·{" "}
                <span className="text-[var(--fg)]">{str(market.quotes_sampled, "0")}</span>
              </p>
              {str(broker.last_error) ? (
                <p className="text-[var(--danger)]">{str(broker.last_error)}</p>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Spread movers</CardTitle>
            </CardHeader>
            <CardContent>
              {spreads.length === 0 ? (
                <DeskEmpty
                  icon={Radio}
                  title="No live spreads"
                  description="Connect MT5 to sample symbol bid/ask from the terminal."
                />
              ) : (
                <DeskTable
                  columns={["Symbol", "Bid", "Ask", "Spread"]}
                  rows={spreads.map((r) => [
                    str(r.symbol),
                    str(r.bid),
                    str(r.ask),
                    str(r.spread),
                  ])}
                />
              )}
            </CardContent>
          </Card>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Positions · {positions.length}</CardTitle>
            </CardHeader>
            <CardContent>
              {positions.length === 0 ? (
                <p className="text-sm text-[var(--fg-muted)]">No open positions in sync.</p>
              ) : (
                <DeskTable
                  columns={["Ticket", "Symbol", "Side", "Volume", "PnL"]}
                  rows={positions.slice(0, 12).map((p) => [
                    str(p.ticket),
                    str(p.symbol),
                    str(p.side),
                    str(p.volume),
                    str(p.profit),
                  ])}
                />
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Pending orders · {pending.length}</CardTitle>
            </CardHeader>
            <CardContent>
              {pending.length === 0 ? (
                <p className="text-sm text-[var(--fg-muted)]">No pending orders in sync.</p>
              ) : (
                <DeskTable
                  columns={["Ticket", "Symbol", "Type", "Volume", "Price"]}
                  rows={pending.slice(0, 12).map((o) => [
                    str(o.ticket),
                    str(o.symbol),
                    str(o.order_type),
                    str(o.volume),
                    str(o.price),
                  ])}
                />
              )}
            </CardContent>
          </Card>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Economic calendar</CardTitle>
              <Badge tone={providers.calendar_configured ? "success" : "neutral"}>
                {providers.calendar_configured ? "feed configured" : "not configured"}
              </Badge>
            </CardHeader>
            <CardContent>
              {events.length === 0 ? (
                <DeskEmpty
                  icon={Newspaper}
                  title="No calendar events"
                  description="Set ECONOMIC_CALENDAR_FEED_URL to a licensed JSON feed. QuantForg will not invent events."
                />
              ) : (
                <DeskTable
                  columns={["When", "Event", "Country", "Impact"]}
                  rows={events.map((e) => [
                    str(e.scheduled_at).slice(0, 16),
                    str(e.title).slice(0, 48),
                    str(e.country),
                    str(e.impact),
                  ])}
                />
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Financial news</CardTitle>
              <Badge tone={providers.news_configured ? "success" : "neutral"}>
                {providers.news_configured ? "feed configured" : "not configured"}
              </Badge>
            </CardHeader>
            <CardContent>
              {news.length === 0 ? (
                <DeskEmpty
                  icon={Newspaper}
                  title="No news items"
                  description="Set NEWS_INTELLIGENCE_FEED_URL to a licensed JSON feed. QuantForg will not invent headlines."
                />
              ) : (
                <DeskTable
                  columns={["Title", "Source", "Published"]}
                  rows={news.map((n) => [
                    str(n.title).slice(0, 56),
                    str(n.source),
                    str(n.published_at).slice(0, 16),
                  ])}
                />
              )}
            </CardContent>
          </Card>
        </div>

        <Card className="mt-4">
          <CardHeader>
            <CardTitle>AI analysis (advisor)</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            {(
              [
                ["Market conditions", asList(analysis.market_conditions)],
                ["Risk factors", asList(analysis.risk_factors)],
                ["News impact", asList(analysis.news_impact)],
                ["Portfolio exposure", asList(analysis.portfolio_exposure)],
              ] as const
            ).map(([title, lines]) => (
              <div key={title}>
                <h3 className="mb-2 text-sm font-medium text-[var(--fg)]">{title}</h3>
                <ul className="space-y-1.5 text-sm text-[var(--fg-muted)]">
                  {lines.map((line, i) => (
                    <li key={i}>• {String(line)}</li>
                  ))}
                </ul>
              </div>
            ))}
            <p className="md:col-span-2 text-xs text-[var(--fg-subtle)]">
              {str(analysis.disclaimer)} Autonomous trading:{" "}
              {analysis.autonomous_trading ? "enabled" : "disabled"}.
            </p>
          </CardContent>
        </Card>
      </PageMotion>
    </div>
  );
}
