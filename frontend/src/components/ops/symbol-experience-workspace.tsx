"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CandlestickChart, Layers3 } from "lucide-react";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { WorkspaceChart } from "@/components/workspace/chart-panel";
import {
  mt5Api,
  signalCenterApi,
  signalIntelligenceApi,
} from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { resolveTradingSymbol } from "@/lib/trading/gold-only";
import { useTradingSession } from "@/providers/trading-session-provider";
import { formatNumber } from "@/lib/utils";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
      <dt className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </dt>
      <dd className="mt-1 font-mono text-[13px] tabular text-[var(--fg)]">{value}</dd>
    </div>
  );
}

/** LIVE symbol desk — never fabricates metrics. */
export function SymbolExperienceWorkspace({ code }: { code: string }) {
  const symbol = resolveTradingSymbol(code);
  const session = useTradingSession();
  const [timeframe, setTimeframe] = useState("H1");
  const [chartType, setChartType] = useState<"candles" | "line" | "area">(
    "candles",
  );
  const [showVolume, setShowVolume] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);

  const tickQ = useQuery({
    queryKey: ["mt5-tick", symbol, "symbol-page"],
    queryFn: () => mt5Api.tick(symbol),
    enabled: Boolean(symbol),
    staleTime: 3_000,
    refetchInterval: 5_000,
    retry: false,
  });
  const signalQ = useQuery({
    queryKey: ["signal-center", symbol],
    queryFn: () => signalCenterApi.get(symbol),
    enabled: Boolean(symbol),
    staleTime: 15_000,
    refetchInterval: 20_000,
    retry: false,
  });
  const historyQ = useQuery({
    queryKey: ["si-history", symbol],
    queryFn: () => signalIntelligenceApi.history({ symbol, limit: 40 }),
    enabled: Boolean(symbol),
    staleTime: 30_000,
    refetchInterval: 45_000,
    retry: false,
  });
  const analyticsQ = useQuery({
    queryKey: ["si-analytics", "symbol-page"],
    queryFn: () => signalIntelligenceApi.analytics(30),
    staleTime: 60_000,
    refetchInterval: 90_000,
    retry: false,
  });

  const tick = asRecord(tickQ.data);
  const signal = asRecord(signalQ.data);
  const historyRows = asList(
    asRecord(historyQ.data).items ||
      asRecord(historyQ.data).history ||
      historyQ.data,
  ).map(asRecord);
  const analytics = asRecord(analyticsQ.data);
  const bySymbol = asList(analytics.by_symbol || analytics.symbols).map(
    asRecord,
  );
  const symbolStats =
    bySymbol.find((r) => str(r.symbol || r.code).toUpperCase() === symbol) ||
    {};

  const positions = useMemo(
    () =>
      session.positions.filter((p) => str(p.symbol).toUpperCase() === symbol),
    [session.positions, symbol],
  );

  const bid = num(tick.bid);
  const ask = num(tick.ask);
  const spread =
    Number.isFinite(bid) && Number.isFinite(ask) ? ask - bid : null;
  const lastPrice = Number.isFinite(num(tick.last))
    ? num(tick.last)
    : Number.isFinite(bid)
      ? bid
      : undefined;

  const loading = tickQ.isLoading && signalQ.isLoading;
  const hardError = tickQ.isError && signalQ.isError && historyQ.isError;

  if (loading) return <DeskSkeleton rows={8} />;
  if (hardError) {
    return (
      <DeskError message="Could not load LIVE tick / signal data for this symbol." />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="font-mono text-[18px] font-semibold text-[var(--fg)]">
            {symbol}
          </h2>
          <Badge
            tone={session.connected ? "success" : "warning"}
            className="h-5"
          >
            {session.connected ? "LIVE" : "Gateway"}
          </Badge>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm" variant="secondary">
            <Link href={`/terminal?symbol=${encodeURIComponent(symbol)}`}>
              Open in Terminal
            </Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/signals">Signal Center</Link>
          </Button>
        </div>
      </div>

      <div className="h-[360px] overflow-hidden border border-[var(--border)]">
        <WorkspaceChart
          symbol={symbol}
          connected={session.connected}
          timeframe={timeframe}
          onTimeframeChange={setTimeframe}
          chartType={chartType}
          onChartTypeChange={setChartType}
          showVolume={showVolume}
          onShowVolumeChange={setShowVolume}
          fullscreen={fullscreen}
          onFullscreenChange={setFullscreen}
          lastPrice={lastPrice}
        />
      </div>

      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
        <Metric
          label="Spread"
          value={spread != null ? formatNumber(spread, 5) : "—"}
        />
        <Metric label="ATR" value={str(signal.atr || signal.atr_value, "—")} />
        <Metric
          label="Trend"
          value={str(
            signal.trend || signal.trend_state || signal.direction,
            "—",
          )}
        />
        <Metric
          label="Momentum"
          value={str(signal.momentum || signal.momentum_score, "—")}
        />
        <Metric
          label="Quality"
          value={str(signal.quality || signal.quality_score, "—")}
        />
        <Metric
          label="Confidence"
          value={str(signal.confidence || signal.confidence_score, "—")}
        />
        <Metric
          label="Probability"
          value={str(signal.probability || signal.win_probability, "—")}
        />
        <Metric
          label="Win Rate"
          value={str(symbolStats.win_rate || symbolStats.winrate, "—")}
        />
        <Metric
          label="Profit Factor"
          value={str(symbolStats.profit_factor || symbolStats.pf, "—")}
        />
        <Metric
          label="Average RR"
          value={str(symbolStats.avg_rr || symbolStats.average_rr, "—")}
        />
        <Metric
          label="Average Hold"
          value={str(symbolStats.avg_hold || symbolStats.average_hold, "—")}
        />
        <Metric label="Open Positions" value={String(positions.length)} />
      </dl>

      <section className="border border-[var(--border)] bg-[var(--surface)]">
        <header className="border-b border-[var(--border)] px-3 py-2">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Open positions
          </h3>
        </header>
        {positions.length === 0 ? (
          <DeskEmpty
            icon={Layers3}
            title="No open positions"
            description={`No LIVE positions for ${symbol}.`}
          />
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {positions.map((p) => (
              <li
                key={str(p.ticket || p.id)}
                className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-[12px]"
              >
                <span className="font-mono">{str(p.ticket || p.id)}</span>
                <span>{str(p.type || p.side)}</span>
                <span className="tabular">{str(p.volume || p.lots)}</span>
                <span className="tabular">{str(p.profit)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)]">
        <header className="border-b border-[var(--border)] px-3 py-2">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Signal history
          </h3>
        </header>
        {historyQ.isLoading ? (
          <DeskSkeleton rows={4} />
        ) : historyRows.length === 0 ? (
          <DeskEmpty
            icon={CandlestickChart}
            title="No signal history"
            description="LIVE history is empty for this symbol."
          />
        ) : (
          <ul className="max-h-72 divide-y divide-[var(--border)] overflow-y-auto">
            {historyRows.map((row, i) => (
              <li
                key={str(row.id || `${i}`)}
                className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-[12px]"
              >
                <span className="tabular text-[var(--fg-subtle)]">
                  {str(row.at || row.timestamp || row.created_at).slice(0, 19)}
                </span>
                <span className="font-medium">
                  {str(row.direction || row.side || row.signal)}
                </span>
                <span className="tabular">
                  {str(row.confidence || row.quality, "—")}
                </span>
                <span className="text-[var(--fg-muted)]">
                  {str(row.outcome || row.result || row.status, "—")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
