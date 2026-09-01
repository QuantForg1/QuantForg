"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { PageMotion } from "@/components/desk/motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { mt5Api, signalIntelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

type Tab =
  | "overview"
  | "history"
  | "outcomes"
  | "probability"
  | "heatmap"
  | "analytics"
  | "overlay";

function fmt(v: unknown, fallback = "—"): string {
  if (v == null || v === "") return fallback;
  return String(v);
}

function heatTone(heat: number): string {
  if (heat >= 85) return "bg-[var(--success)]/80";
  if (heat >= 70) return "bg-[var(--accent)]/70";
  if (heat >= 55) return "bg-[var(--warning)]/60";
  return "bg-[var(--surface-2)]";
}

export function SignalIntelligenceWorkspace({
  initialTab = "overview",
}: {
  initialTab?: Tab;
}) {
  const [tab, setTab] = useState<Tab>(initialTab);

  useEffect(() => {
    setTab(initialTab);
  }, [initialTab]);
  const [symbol, setSymbol] = useState("XAUUSD");
  const [days, setDays] = useState(30);

  const overview = useQuery({
    queryKey: ["si-v2-overview", days],
    queryFn: () => signalIntelligenceApi.overview(days),
    refetchInterval: 30_000,
    enabled: tab === "overview",
  });
  const history = useQuery({
    queryKey: ["si-v2-history", symbol],
    queryFn: () =>
      signalIntelligenceApi.history({ symbol: symbol || undefined, limit: 200 }),
    refetchInterval: 30_000,
    enabled: tab === "history" || tab === "overlay",
  });
  const outcomes = useQuery({
    queryKey: ["si-v2-outcomes", days],
    queryFn: () => signalIntelligenceApi.outcomes(Math.min(days, 14), 100),
    refetchInterval: 30_000,
    enabled: tab === "outcomes",
  });
  const probability = useQuery({
    queryKey: ["si-v2-probability"],
    queryFn: () => signalIntelligenceApi.probability(),
    refetchInterval: 20_000,
    enabled: tab === "probability",
  });
  const heatmap = useQuery({
    queryKey: ["si-v2-heatmap"],
    queryFn: () => signalIntelligenceApi.heatmap(),
    refetchInterval: 20_000,
    enabled: tab === "heatmap",
  });
  const analytics = useQuery({
    queryKey: ["si-v2-analytics", days],
    queryFn: () => signalIntelligenceApi.analytics(days),
    refetchInterval: 45_000,
    enabled: tab === "analytics" || tab === "overview",
  });

  const tabs: Array<{ id: Tab; label: string }> = [
    { id: "overview", label: "Overview" },
    { id: "history", label: "Signal History" },
    { id: "outcomes", label: "Outcomes" },
    { id: "probability", label: "Probability" },
    { id: "heatmap", label: "Heat Map" },
    { id: "analytics", label: "Analytics" },
    { id: "overlay", label: "Chart Overlay" },
  ];

  const agg = (
    ((overview.data?.analytics as Record<string, unknown> | undefined)
      ?.aggregate as Record<string, unknown> | undefined) ??
    (analytics.data?.aggregate as Record<string, unknown> | undefined) ??
    {}
  ) as Record<string, unknown>;

  return (
    <PageMotion>
      <div className="space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap gap-2">
            {tabs.map((t) => (
              <Button
                key={t.id}
                size="sm"
                variant={tab === t.id ? "default" : "outline"}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </Button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className="w-28 font-mono"
              aria-label="Symbol"
            />
            <select
              className="border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-sm"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              aria-label="Lookback days"
            >
              {[7, 14, 30, 90].map((d) => (
                <option key={d} value={d}>
                  {d}d
                </option>
              ))}
            </select>
            <Badge tone="accent">LIVE only · never fabricated</Badge>
          </div>
        </div>

        {tab === "overview" ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {(
                [
                  ["LIVE signals", (overview.data?.live_signals as Record<string, unknown> | undefined)?.count],
                  ["Win rate", agg.win_rate != null ? `${agg.win_rate}%` : "—"],
                  [
                    "Profit factor",
                    agg.profit_factor ?? (agg.profit_factor_infinite ? "∞" : "—"),
                  ],
                  ["Avg hold (min)", agg.average_hold_minutes ?? "—"],
                ] as Array<[string, unknown]>
              ).map(([k, v]) => (
                <div
                  key={k}
                  className="border border-[var(--border)] bg-[var(--surface)] px-4 py-3"
                >
                  <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                    {k}
                  </p>
                  <p className="mt-1 font-mono text-2xl text-[var(--fg)]">{fmt(v)}</p>
                </div>
              ))}
            </div>
            <p className="text-[11px] text-[var(--fg-subtle)]">
              KPI source: LIVE MT5 closed deals / production stats · fabricated=
              {fmt(overview.data?.fabricated ?? false)}
            </p>
            <AnalyticsTable
              items={asList(
                ((overview.data?.analytics as Record<string, unknown> | undefined)
                  ?.items) ?? analytics.data?.items,
              )}
            />
          </div>
        ) : null}

        {tab === "history" ? (
          <HistoryTable items={asList(history.data?.items)} />
        ) : null}

        {tab === "outcomes" ? (
          <OutcomesTable items={asList(outcomes.data?.items)} meta={outcomes.data} />
        ) : null}

        {tab === "probability" ? (
          <ProbabilityPanel items={asList(probability.data?.items)} />
        ) : null}

        {tab === "heatmap" ? (
          <HeatMapPanel cells={asList(heatmap.data?.cells)} asOf={fmt(heatmap.data?.as_of)} />
        ) : null}

        {tab === "analytics" ? (
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {(
                [
                  ["Closed", agg.closed_trades],
                  ["WR%", agg.win_rate],
                  ["PF", agg.profit_factor ?? (agg.profit_factor_infinite ? "∞" : null)],
                  ["Net", agg.net_pnl],
                  ["Avg hold m", agg.average_hold_minutes],
                ] as Array<[string, unknown]>
              ).map(([k, v]) => (
                <div
                  key={k}
                  className="border border-[var(--border)] bg-[var(--surface)] px-3 py-3"
                >
                  <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                    {k}
                  </p>
                  <p className="mt-1 font-mono text-xl">{fmt(v)}</p>
                </div>
              ))}
            </div>
            <AnalyticsTable items={asList(analytics.data?.items)} />
          </div>
        ) : null}

        {tab === "overlay" ? (
          <ChartOverlayPanel symbol={symbol || "XAUUSD"} />
        ) : null}
      </div>
    </PageMotion>
  );
}

function AnalyticsTable({ items }: { items: unknown[] }) {
  const rows = items.map(asRecord);
  if (!rows.length) {
    return (
      <Empty>
        No LIVE closed-trade analytics yet. KPIs appear after real MT5 closes —
        never simulated.
      </Empty>
    );
  }
  return (
    <div className="overflow-x-auto border border-[var(--border)] bg-[var(--surface)]">
      <table className="w-full min-w-[880px] text-left text-sm">
        <thead className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          <tr>
            <th className="px-3 py-2">Symbol</th>
            <th className="px-3 py-2">Win rate</th>
            <th className="px-3 py-2">Profit factor</th>
            <th className="px-3 py-2">Avg RR</th>
            <th className="px-3 py-2">Avg hold</th>
            <th className="px-3 py-2">Trades</th>
            <th className="px-3 py-2">Net</th>
            <th className="px-3 py-2">Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={str(r.symbol)} className="border-b border-[var(--border)]/60">
              <td className="px-3 py-2 font-mono font-semibold">{str(r.symbol)}</td>
              <td className="px-3 py-2 font-mono">
                {r.win_rate == null ? "—" : `${r.win_rate}%`}
              </td>
              <td className="px-3 py-2 font-mono">
                {r.profit_factor == null
                  ? r.profit_factor_infinite
                    ? "∞"
                    : "—"
                  : String(r.profit_factor)}
              </td>
              <td className="px-3 py-2 font-mono">{fmt(r.average_rr)}</td>
              <td className="px-3 py-2 font-mono">
                {fmt(r.average_hold_minutes)}
              </td>
              <td className="px-3 py-2 font-mono">{fmt(r.closed_trades)}</td>
              <td
                className={cn(
                  "px-3 py-2 font-mono",
                  num(r.net_pnl) > 0 && "text-[var(--success)]",
                  num(r.net_pnl) < 0 && "text-[var(--danger)]",
                )}
              >
                {fmt(r.net_pnl)}
              </td>
              <td className="px-3 py-2 text-[10px] text-[var(--fg-subtle)]">
                {fmt(r.kpi_source)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HistoryTable({ items }: { items: unknown[] }) {
  const rows = items.map(asRecord);
  if (!rows.length) {
    return (
      <Empty>
        No observed LIVE signals yet. History fills when the XAUUSD (Gold) scan
        publishes scores.
      </Empty>
    );
  }
  return (
    <div className="overflow-x-auto border border-[var(--border)] bg-[var(--surface)]">
      <table className="w-full min-w-[960px] text-left text-sm">
        <thead className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          <tr>
            <th className="px-3 py-2">Time</th>
            <th className="px-3 py-2">Symbol</th>
            <th className="px-3 py-2">Dir</th>
            <th className="px-3 py-2">Badge</th>
            <th className="px-3 py-2">Q</th>
            <th className="px-3 py-2">C</th>
            <th className="px-3 py-2">Prob</th>
            <th className="px-3 py-2">Session</th>
            <th className="px-3 py-2">Gate</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={`${str(r.symbol)}-${str(r.scan_as_of)}-${i}`}
              className="border-b border-[var(--border)]/60"
            >
              <td className="px-3 py-2 font-mono text-[10px]">{fmt(r.observed_at)}</td>
              <td className="px-3 py-2 font-mono font-semibold">{str(r.symbol)}</td>
              <td className="px-3 py-2 font-mono">{str(r.direction)}</td>
              <td className="px-3 py-2">
                <Badge tone="neutral">{fmt(r.badge)}</Badge>
              </td>
              <td className="px-3 py-2 font-mono">{fmt(r.quality)}</td>
              <td className="px-3 py-2 font-mono">{fmt(r.confidence)}</td>
              <td className="px-3 py-2 font-mono">{fmt(r.probability)}</td>
              <td className="px-3 py-2 font-mono text-xs">{fmt(r.session)}</td>
              <td className="max-w-[180px] truncate px-3 py-2 text-[11px] text-[var(--fg-muted)]">
                {fmt(r.blocking_gate)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OutcomesTable({
  items,
  meta,
}: {
  items: unknown[];
  meta?: Record<string, unknown>;
}) {
  const rows = items.map(asRecord);
  return (
    <div className="space-y-3">
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Soft-join window {fmt(meta?.join_window_sec)}s · matched{" "}
        {fmt(meta?.matched_count)} · fabricated={fmt(meta?.fabricated)}
      </p>
      {!rows.length ? (
        <Empty>No outcome rows yet from LIVE signal→deal joins.</Empty>
      ) : (
        <div className="overflow-x-auto border border-[var(--border)] bg-[var(--surface)]">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              <tr>
                <th className="px-3 py-2">Signal</th>
                <th className="px-3 py-2">Symbol</th>
                <th className="px-3 py-2">Dir</th>
                <th className="px-3 py-2">Join</th>
                <th className="px-3 py-2">Result</th>
                <th className="px-3 py-2">PnL</th>
                <th className="px-3 py-2">Hold s</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const outcome = asRecord(r.outcome);
                return (
                  <tr key={`${str(r.symbol)}-${i}`} className="border-b border-[var(--border)]/60">
                    <td className="px-3 py-2 font-mono text-[10px]">
                      {fmt(r.signal_time)}
                    </td>
                    <td className="px-3 py-2 font-mono font-semibold">
                      {str(r.symbol)}
                    </td>
                    <td className="px-3 py-2 font-mono">{str(r.direction)}</td>
                    <td className="px-3 py-2 text-xs">{fmt(r.join_status)}</td>
                    <td className="px-3 py-2 font-mono">{fmt(outcome.result)}</td>
                    <td className="px-3 py-2 font-mono">{fmt(outcome.profit_loss)}</td>
                    <td className="px-3 py-2 font-mono">
                      {fmt(outcome.holding_time_sec)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ProbabilityPanel({ items }: { items: unknown[] }) {
  const rows = items.map(asRecord);
  if (!rows.length) return <Empty>No LIVE probabilities in current scan.</Empty>;
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {rows.map((r) => (
        <div
          key={str(r.symbol)}
          className="border border-[var(--border)] bg-[var(--surface)] p-4"
        >
          <div className="flex items-center justify-between">
            <span className="font-mono text-lg font-semibold">{str(r.symbol)}</span>
            <Badge tone="accent">{fmt(r.badge)}</Badge>
          </div>
          <p className="mt-3 font-mono text-3xl text-[var(--accent)]">
            {fmt(r.probability)}%
          </p>
          <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
            {str(r.direction)} · Q{fmt(r.quality)} · C{fmt(r.confidence)}
          </p>
          <div className="mt-3 h-1.5 w-full bg-[var(--surface-2)]">
            <div
              className="h-full bg-[var(--accent)]"
              style={{
                width: `${Math.min(100, Math.max(0, num(r.probability)))}%`,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function HeatMapPanel({ cells, asOf }: { cells: unknown[]; asOf: string }) {
  const rows = cells.map(asRecord);
  if (!rows.length) return <Empty>Heat map empty — waiting for LIVE scan.</Empty>;
  return (
    <div className="space-y-3">
      <p className="text-[11px] text-[var(--fg-subtle)]">as_of {asOf}</p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6">
        {rows.map((c) => (
          <div
            key={str(c.symbol)}
            className={cn(
              "border border-[var(--border)] p-3",
              heatTone(num(c.heat)),
            )}
          >
            <div className="flex items-center justify-between gap-1">
              <span className="font-mono text-sm font-semibold text-[var(--fg)]">
                {str(c.symbol)}
              </span>
              <span className="font-mono text-[10px]">{str(c.direction)}</span>
            </div>
            <p className="mt-2 font-mono text-lg">{fmt(c.heat)}</p>
            <p className="text-[10px] text-[var(--fg)]/80">
              Q{fmt(c.quality)} C{fmt(c.confidence)} P{fmt(c.probability)}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChartOverlayPanel({ symbol }: { symbol: string }) {
  const host = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  const candles = useQuery({
    queryKey: ["si-v2-candles", symbol],
    queryFn: () => mt5Api.candles(symbol, "M15", 180),
    refetchInterval: 30_000,
  });
  const markers = useQuery({
    queryKey: ["si-v2-markers", symbol],
    queryFn: () => signalIntelligenceApi.chartMarkers(symbol, 50),
    refetchInterval: 30_000,
  });

  const points = useMemo(() => {
    const rows = asList(candles.data).map(asRecord);
    const out: Array<{
      time: UTCTimestamp;
      open: number;
      high: number;
      low: number;
      close: number;
    }> = [];
    for (const r of rows) {
      const t = Date.parse(str(r.open_time));
      if (!Number.isFinite(t)) continue;
      const open = num(r.open);
      const high = num(r.high);
      const low = num(r.low);
      const close = num(r.close);
      if (![open, high, low, close].every(Number.isFinite)) continue;
      out.push({
        time: Math.floor(t / 1000) as UTCTimestamp,
        open,
        high,
        low,
        close,
      });
    }
    out.sort((a, b) => a.time - b.time);
    return out;
  }, [candles.data]);

  useEffect(() => {
    if (!host.current) return;
    const chart = createChart(host.current, {
      height: 420,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "rgba(148,163,184,0.12)" },
        horzLines: { color: "rgba(148,163,184,0.12)" },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#16a34a",
      downColor: "#dc2626",
      borderVisible: false,
      wickUpColor: "#16a34a",
      wickDownColor: "#dc2626",
    });
    chartRef.current = chart;
    seriesRef.current = series;
    const ro = new ResizeObserver(() => {
      if (!host.current) return;
      chart.applyOptions({ width: host.current.clientWidth });
    });
    ro.observe(host.current);
    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || !points.length) return;
    seriesRef.current.setData(points);
    const rawMarkers = asList(markers.data?.markers).map(asRecord);
    const mapped = rawMarkers
      .map((m) => ({
        time: Number(m.time) as UTCTimestamp,
        position: (str(m.position) || "aboveBar") as
          | "aboveBar"
          | "belowBar"
          | "inBar",
        color: str(m.color) || "#ff5a1f",
        shape: (str(m.shape) || "circle") as
          | "circle"
          | "square"
          | "arrowUp"
          | "arrowDown",
        text: str(m.text),
      }))
      .filter((m) => Number.isFinite(m.time))
      .sort((a, b) => a.time - b.time);
    try {
      // lightweight-charts v5 series markers API
      (seriesRef.current as unknown as { setMarkers?: (m: unknown[]) => void }).setMarkers?.(
        mapped,
      );
    } catch {
      /* markers optional if series API differs */
    }
    chartRef.current?.timeScale().fitContent();
  }, [points, markers.data]);

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-[var(--fg-subtle)]">
        {symbol} M15 · LIVE candles + observed signal markers · fabricated=
        {fmt(markers.data?.fabricated)}
      </p>
      <div
        ref={host}
        className="w-full border border-[var(--border)] bg-[var(--surface)]"
      />
      {!points.length ? (
        <Empty>Waiting for LIVE candles for {symbol}.</Empty>
      ) : null}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="border border-[var(--border)] bg-[var(--surface)] px-6 py-12 text-center text-[var(--fg-muted)]">
      {children}
    </div>
  );
}
