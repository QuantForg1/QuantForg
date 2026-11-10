"use client";

import { displayTradingSymbol } from "@/lib/trading/gold-only";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import {
  AreaSeries,
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useQuery } from "@tanstack/react-query";
import {
  Maximize2,
  Minimize2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { mt5Api } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";
import {
  candleLoadErrorMessage,
  publicFeedBadge,
} from "@/lib/trading/market-status";
import { useTradingSessionOptional } from "@/providers/trading-session-provider";

const TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"] as const;

type ChartType = "candles" | "line" | "area";

type CandlePoint = {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

function parseCandles(raw: unknown): CandlePoint[] {
  const rows = asList(raw).map(asRecord);
  const points: CandlePoint[] = [];
  for (const r of rows) {
    const t = Date.parse(str(r.open_time));
    if (!Number.isFinite(t)) continue;
    const open = num(r.open);
    const high = num(r.high);
    const low = num(r.low);
    const close = num(r.close);
    if (![open, high, low, close].every(Number.isFinite)) continue;
    points.push({
      time: Math.floor(t / 1000) as UTCTimestamp,
      open,
      high,
      low,
      close,
      volume: num(r.tick_volume, 0),
    });
  }
  points.sort((a, b) => a.time - b.time);
  const dedup: CandlePoint[] = [];
  for (const p of points) {
    if (dedup.length && dedup[dedup.length - 1].time === p.time) {
      dedup[dedup.length - 1] = p;
    } else {
      dedup.push(p);
    }
  }
  return dedup;
}

export const WorkspaceChart = memo(function WorkspaceChart({
  symbol,
  connected,
  marketFeedEnabled = true,
  timeframe,
  onTimeframeChange,
  chartType,
  onChartTypeChange,
  showVolume,
  onShowVolumeChange,
  fullscreen,
  onFullscreenChange,
  lastPrice,
  hideSymbolLabel = false,
}: {
  symbol: string;
  /** Customer broker session — kept for callers; chart feed is independent. */
  connected: boolean;
  /** When true, load platform research candles without requiring MT5 ownership. */
  marketFeedEnabled?: boolean;
  timeframe: string;
  onTimeframeChange: (tf: string) => void;
  chartType: ChartType;
  onChartTypeChange: (t: ChartType) => void;
  showVolume: boolean;
  onShowVolumeChange: (v: boolean) => void;
  fullscreen: boolean;
  onFullscreenChange: (v: boolean) => void;
  lastPrice?: number;
  /** Parent owns the symbol title (Overview / Signals headers). */
  hideSymbolLabel?: boolean;
}) {
  const session = useTradingSessionOptional();
  // Broker ownership remains available to callers; candles use the platform feed.
  void connected;
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const mainRef = useRef<ISeriesApi<"Candlestick"> | ISeriesApi<"Line"> | ISeriesApi<"Area"> | null>(
    null,
  );
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const [ohlc, setOhlc] = useState<CandlePoint | null>(null);
  const candlesCache = useRef<CandlePoint[]>([]);

  const candlesQ = useQuery({
    queryKey: ["public-market-candles", symbol, timeframe],
    queryFn: async () => {
      try {
        return await mt5Api.publicCandles(symbol, timeframe, 400);
      } catch {
        // Authenticated fallback to research path when public route is unavailable.
        const rows = await mt5Api.researchCandles(symbol, timeframe, 400);
        return {
          ok: true,
          status: "live",
          source: "mt5_research",
          as_of: null,
          candles: rows,
          note: "Authenticated research feed.",
        };
      }
    },
    retry: 1,
    enabled: marketFeedEnabled && Boolean(symbol),
    staleTime: 60_000,
    refetchInterval: marketFeedEnabled ? 60_000 : false,
  });

  const feedMeta = asRecord(candlesQ.data);
  const candles = useMemo(
    () => parseCandles(feedMeta.candles ?? candlesQ.data),
    [candlesQ.data, feedMeta.candles],
  );
  const feedStatus = candlesQ.isLoading
    ? "loading"
    : str(feedMeta.status || (candles.length ? "live" : "unavailable"));
  const feedBadge = publicFeedBadge(feedStatus);
  const feedLive = candlesQ.isSuccess && candles.length > 0 && feedStatus === "live";
  const asOf = str(feedMeta.as_of || "");

  useEffect(() => {
    candlesCache.current = candles;
    if (candles.length) setOhlc(candles[candles.length - 1]);
  }, [candles]);

  useEffect(() => {
    if (!Number.isFinite(lastPrice) || lastPrice == null || !mainRef.current) return;
    const series = candlesCache.current;
    if (!series.length) return;
    const last = { ...series[series.length - 1] };
    last.close = lastPrice;
    last.high = Math.max(last.high, lastPrice);
    last.low = Math.min(last.low, lastPrice);
    series[series.length - 1] = last;
    setOhlc(last);
    if (chartType === "candles") {
      (mainRef.current as ISeriesApi<"Candlestick">).update({
        time: last.time,
        open: last.open,
        high: last.high,
        low: last.low,
        close: last.close,
      });
    } else {
      (mainRef.current as ISeriesApi<"Line"> | ISeriesApi<"Area">).update({
        time: last.time,
        value: last.close,
      });
    }
  }, [lastPrice, chartType]);

  useEffect(() => {
    const el = hostRef.current;
    if (!el) return;

    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "rgba(226, 232, 240, 0.72)",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(148, 163, 184, 0.08)" },
        horzLines: { color: "rgba(148, 163, 184, 0.08)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
    });
    chartRef.current = chart;

    let main: ISeriesApi<"Candlestick"> | ISeriesApi<"Line"> | ISeriesApi<"Area">;
    if (chartType === "candles") {
      main = chart.addSeries(CandlestickSeries, {
        upColor: "#14b8a6",
        downColor: "#f43f5e",
        borderUpColor: "#14b8a6",
        borderDownColor: "#f43f5e",
        wickUpColor: "#14b8a6",
        wickDownColor: "#f43f5e",
      });
      main.setData(
        candles.map((c) => ({
          time: c.time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        })),
      );
    } else if (chartType === "line") {
      main = chart.addSeries(LineSeries, {
        color: "#00D4E0",
        lineWidth: 2,
      });
      main.setData(candles.map((c) => ({ time: c.time, value: c.close })));
    } else {
      main = chart.addSeries(AreaSeries, {
        lineColor: "#00D4E0",
        topColor: "rgba(0, 212, 224, 0.28)",
        bottomColor: "rgba(0, 212, 224, 0.02)",
        lineWidth: 2,
      });
      main.setData(candles.map((c) => ({ time: c.time, value: c.close })));
    }
    mainRef.current = main;

    if (showVolume) {
      const volume = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volume.setData(
        candles.map((c) => ({
          time: c.time,
          value: c.volume,
          color:
            c.close >= c.open
              ? "rgba(20, 184, 166, 0.35)"
              : "rgba(244, 63, 94, 0.35)",
        })),
      );
      volumeRef.current = volume;
    }

    if (el.clientWidth > 0 && el.clientHeight > 0) {
      chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
      chart.timeScale().fitContent();
    }

    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !mainRef.current) {
        const last = candlesCache.current[candlesCache.current.length - 1];
        if (last) setOhlc(last);
        return;
      }
      const hit = candlesCache.current.find((c) => c.time === param.time);
      if (hit) setOhlc(hit);
    });

    return () => {
      chart.remove();
      chartRef.current = null;
      mainRef.current = null;
      volumeRef.current = null;
    };
  }, [chartType, showVolume, candles]);

  return (
    <section
      className="flex h-full min-h-0 flex-col bg-[var(--bg)]"
      aria-label={`${displayTradingSymbol(symbol)} chart workspace`}
    >
      <div className="flex h-9 shrink-0 items-center gap-2 border-b border-[var(--border)]/70 px-2">
        {!hideSymbolLabel ? (
          <>
            <p className="text-xs font-semibold tracking-tight text-[var(--fg)]">
              {displayTradingSymbol(symbol)}
            </p>
            <span
              className="qf-status-dot"
              data-state={feedBadge.tone === "ok" ? "ok" : feedBadge.tone === "danger" ? "danger" : "warn"}
              aria-label={feedBadge.label}
            />
            <span className="rounded border border-[var(--border)] px-1.5 py-0.5 text-[9px] font-semibold tracking-wide text-[var(--fg-muted)]">
              {feedBadge.label}
            </span>
          </>
        ) : (
          <span className="rounded border border-[var(--border)] px-1.5 py-0.5 text-[9px] font-semibold tracking-wide text-[var(--fg-muted)]">
            {feedBadge.label}
          </span>
        )}
        {ohlc ? (
          <p
            className="hidden min-w-0 truncate tabular text-[10px] text-[var(--fg-muted)] lg:inline"
            aria-live="polite"
          >
            O {formatNumber(ohlc.open, 2)} · H {formatNumber(ohlc.high, 2)} · L{" "}
            {formatNumber(ohlc.low, 2)} · C {formatNumber(ohlc.close, 2)}
            {asOf ? ` · ${asOf}` : ""}
          </p>
        ) : null}
        <div className="ml-auto flex shrink-0 items-center gap-0.5">
          <div className="flex gap-0.5" role="group" aria-label="Timeframe">
            {TIMEFRAMES.map((tf) => (
              <Button
                key={tf}
                size="sm"
                variant={timeframe === tf ? "secondary" : "ghost"}
                className="h-6 min-w-[1.75rem] px-1.5 text-[10px]"
                data-compact
                onClick={() => onTimeframeChange(tf)}
                aria-pressed={timeframe === tf}
              >
                {tf}
              </Button>
            ))}
          </div>
          <div className="hidden gap-0.5 sm:flex" role="group" aria-label="Chart type">
            {(
              [
                ["candles", "C"],
                ["line", "L"],
                ["area", "A"],
              ] as const
            ).map(([id, label]) => (
              <Button
                key={id}
                size="sm"
                variant={chartType === id ? "secondary" : "ghost"}
                className="h-6 w-6 px-0 text-[10px]"
                data-compact
                onClick={() => onChartTypeChange(id)}
                aria-label={id}
                aria-pressed={chartType === id}
              >
                {label}
              </Button>
            ))}
          </div>
          <Button
            size="sm"
            variant={showVolume ? "secondary" : "ghost"}
            className="h-6 px-1.5 text-[10px]"
            data-compact
            onClick={() => onShowVolumeChange(!showVolume)}
            aria-pressed={showVolume}
          >
            Vol
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-6 w-6 px-0"
            data-compact
            onClick={() => onFullscreenChange(!fullscreen)}
            aria-label={fullscreen ? "Exit fullscreen chart" : "Fullscreen chart"}
          >
            {fullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </div>

      <div className="relative min-h-[280px] flex-1">
        {candlesQ.isLoading ? (
          <div className="p-4">
            <DeskSkeleton rows={6} />
          </div>
        ) : candles.length > 0 ? (
          <>
            {(feedStatus === "closed" || feedStatus === "delayed") && (
              <div className="pointer-events-none absolute left-3 top-3 z-10 rounded border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg)_88%,transparent)] px-2 py-1 text-[10px] font-medium text-[var(--fg-muted)] backdrop-blur">
                {feedStatus === "closed"
                  ? "MARKET CLOSED — showing last available candles"
                  : "DELAYED — licensed reference data (not broker execution)"}
                {asOf ? ` · ${asOf}` : ""}
              </div>
            )}
            <div
              ref={hostRef}
              className="absolute inset-0 min-h-[280px]"
              role="img"
              aria-label={`${displayTradingSymbol(symbol)} price chart`}
            />
          </>
        ) : candlesQ.isError ? (
          <div className="flex h-full min-h-[280px] flex-col items-center justify-center gap-3 p-6 text-center">
            <DeskError
              message={candleLoadErrorMessage(
                candlesQ.error,
                symbol,
                session?.gatewayOnline ?? null,
              )}
              onRetry={() => candlesQ.refetch()}
            />
            <p className="max-w-sm text-xs text-[var(--fg-muted)]">
              Live Market uses the platform feed and does not require your personal MT5
              account.
            </p>
          </div>
        ) : (
          <div className="flex h-full min-h-[280px] flex-col items-center justify-center gap-3 p-6 text-center">
            <p className="text-sm text-[var(--fg-muted)]">
              No genuine candle history available for {displayTradingSymbol(symbol)} (
              {timeframe}).
            </p>
            <Button size="sm" variant="secondary" onClick={() => candlesQ.refetch()}>
              Retry
            </Button>
          </div>
        )}
      </div>
    </section>
  );
});
