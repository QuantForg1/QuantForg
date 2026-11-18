"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { PageMotion } from "@/components/desk/motion";
import { intelligenceApi, mt5Api } from "@/lib/api/endpoints";
import { SessionStrip } from "@/components/broker/session-strip";
import { OverviewMarketIntelligence } from "@/components/trading/overview-market-intelligence";
import { useTradingSession } from "@/providers/trading-session-provider";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";

export default function MarketIntelligencePage() {
  const session = useTradingSession();
  const dash = useQuery({
    queryKey: ["intelligence-dashboard"],
    queryFn: () => intelligenceApi.dashboard("FX"),
    retry: false,
    refetchInterval: 45_000,
    staleTime: 12_000,
  });
  const contextQ = useQuery({
    queryKey: ["intelligence-market-context"],
    queryFn: () => intelligenceApi.marketContext("FX"),
    retry: false,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  const tickQ = useQuery({
    queryKey: ["research-tick", TRADING_SYMBOL],
    queryFn: async () => {
      try {
        return await mt5Api.publicTick(TRADING_SYMBOL);
      } catch {
        return mt5Api.researchTick(TRADING_SYMBOL);
      }
    },
    retry: 1,
    staleTime: 5_000,
    refetchInterval: 10_000,
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
  const context = {
    ...asRecord(data.market_context),
    ...asRecord(contextQ.data),
  };
  const market = asRecord(data.market);
  const analysis = asRecord(data.analysis);
  const positions = asList(data.positions).map(asRecord);
  const pending = asList(data.pending_orders).map(asRecord);
  const news = asList(data.news).map(asRecord);
  const events = asList(data.economic_events).map(asRecord);
  const spreads = asList(market.spread_movers).map(asRecord);
  const tickEnvelope = asRecord(tickQ.data);
  const tick = asRecord(tickEnvelope.tick ?? tickQ.data);
  const bid = num(tick.bid);
  const ask = num(tick.ask);
  const tickMid =
    Number.isFinite(bid) && Number.isFinite(ask)
      ? (bid + ask) / 2
      : Number.isFinite(bid)
        ? bid
        : Number.isFinite(ask)
          ? ask
          : NaN;
  const analysisGroups = (
    [
      ["Market conditions", asList(analysis.market_conditions)],
      ["Risk factors", asList(analysis.risk_factors)],
      ["News impact", asList(analysis.news_impact)],
      ["Portfolio exposure", asList(analysis.portfolio_exposure)],
    ] as const
  ).filter(([, lines]) => lines.length > 0);

  return (
    <div className="mx-auto w-full min-w-0 max-w-6xl">
      <PageHeader
        eyebrow="Markets"
        title="Market Intelligence"
        description="XAUUSD structure from the live feed, plus broker context that the intelligence service actually returns."
        actions={
          <Button asChild size="sm" variant="secondary">
            <a href="/ai-trading-intelligence">Research desks</a>
          </Button>
        }
      />
      <SessionStrip className="mb-4" />
      <PageMotion className="space-y-4">
        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <Card className="qf-card-interactive">
            <CardHeader>
              <CardTitle>Market overview</CardTitle>
            </CardHeader>
            <CardContent>
              <OverviewMarketIntelligence
                timeframe="M15"
                lastPrice={Number.isFinite(tickMid) ? tickMid : undefined}
                marketFeedStatus={str(tickEnvelope.status || (Number.isFinite(tickMid) ? "live" : "unavailable"))}
                tickUpdatedAt={tickQ.dataUpdatedAt || undefined}
                tickTime={str(tick.time || tick.timestamp || tickEnvelope.as_of || "")}
                tickLoading={tickQ.isLoading}
                tickError={tickQ.isError}
                support=""
                resistance=""
                confidencePct={null}
                signalDirection="WAIT"
              />
            </CardContent>
          </Card>
          <Card className="qf-card-interactive">
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Feed health</CardTitle>
              <Badge tone={broker.connected || session.connected ? "success" : "warning"}>
                {broker.connected || session.connected ? "Connected" : "Disconnected"}
              </Badge>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              {[
                ["Desk session", str(context.session, "")],
                ["Volatility", str(context.volatility_level, "")],
                ["Liquidity", str(context.liquidity_level, "")],
                [
                  "Latency",
                  Number.isFinite(num(broker.latency_ms))
                    ? `${formatNumber(num(broker.latency_ms), 0)} ms`
                    : "",
                ],
              ]
                .filter(([, value]) => value && value !== "—")
                .map(([label, value]) => (
                  <div key={label} className="min-w-0">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
                      {label}
                    </p>
                    <p className="mt-1 truncate text-sm font-semibold text-[var(--fg)]">{value}</p>
                  </div>
                ))}
              {str(broker.last_error) ? (
                <p className="col-span-2 text-sm text-[var(--danger)]">{str(broker.last_error)}</p>
              ) : null}
            </CardContent>
          </Card>
        </div>
        {spreads.length > 0 ? (
        <div>
          <Card>
            <CardHeader>
              <CardTitle>Spread movers</CardTitle>
            </CardHeader>
            <CardContent>
                <DeskTable
                  columns={["Symbol", "Bid", "Ask", "Spread"]}
                  rows={spreads.map((r) => [
                    str(r.symbol),
                    str(r.bid),
                    str(r.ask),
                    str(r.spread),
                  ])}
                />
            </CardContent>
          </Card>
        </div>
        ) : null}

        {positions.length > 0 || pending.length > 0 ? (
        <div className={positions.length > 0 && pending.length > 0 ? "grid gap-4 xl:grid-cols-2" : undefined}>
          {positions.length > 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>Positions · {positions.length}</CardTitle>
            </CardHeader>
            <CardContent>
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
            </CardContent>
          </Card>
          ) : null}
          {pending.length > 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>Pending orders · {pending.length}</CardTitle>
            </CardHeader>
            <CardContent>
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
            </CardContent>
          </Card>
          ) : null}
        </div>
        ) : null}

        {events.length > 0 || news.length > 0 ? (
        <div className={events.length > 0 && news.length > 0 ? "grid items-start gap-4 xl:grid-cols-2" : undefined}>
          {events.length > 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>Economic calendar</CardTitle>
            </CardHeader>
            <CardContent>
                <DeskTable
                  columns={["When", "Event", "Country", "Impact"]}
                  rows={events.map((e) => [
                    str(e.scheduled_at).slice(0, 16),
                    str(e.title).slice(0, 48),
                    str(e.country),
                    str(e.impact),
                  ])}
                />
            </CardContent>
          </Card>
          ) : null}
          {news.length > 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>Financial news</CardTitle>
            </CardHeader>
            <CardContent>
                <DeskTable
                  columns={["Title", "Source", "Published"]}
                  rows={news.map((n) => [
                    str(n.title).slice(0, 56),
                    str(n.source),
                    str(n.published_at).slice(0, 16),
                  ])}
                />
            </CardContent>
          </Card>
          ) : null}
        </div>
        ) : null}

        {analysisGroups.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Research notes</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            {analysisGroups.map(([title, lines]) => (
              <div key={title}>
                <h3 className="mb-2 text-sm font-medium text-[var(--fg)]">{title}</h3>
                <ul className="space-y-1.5 text-sm text-[var(--fg-muted)]">
                  {lines.map((line, i) => (
                    <li key={i}>{String(line)}</li>
                  ))}
                </ul>
              </div>
            ))}
            {str(analysis.disclaimer) ? (
              <p className="md:col-span-2 text-xs text-[var(--fg-subtle)]">
                {str(analysis.disclaimer)}
              </p>
            ) : null}
          </CardContent>
        </Card>
        ) : null}
      </PageMotion>
    </div>
  );
}
