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
import { applyLivePrice, clockOffsetSeconds, TIMEFRAME_SECONDS } from "@/lib/market/live-candles";
import { useQuery } from "@tanstack/react-query";
import {
  Maximize2,
  Minimize2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { DeskSkeleton } from "@/components/desk/primitives";
import { mt5Api } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn, formatNumber } from "@/lib/utils";
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
  comfortable = false,
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
  /** Larger, wrapping toolbar for the Overview chart only. */
  comfortable?: boolean;
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
    retry: 2,
    retryDelay: (n) => Math.min(1000 * 2 ** n, 8000),
    enabled: marketFeedEnabled && Boolean(symbol),
    staleTime: 15_000,
    // Live price updates the forming bar every ~2 s; a full refresh keeps
    // closed bars exact (shorter timeframes refresh more often).
    refetchInterval: marketFeedEnabled
      ? timeframe === "M1" || timeframe === "M5"
        ? 20_000
        : 60_000
      : false,
  });

  // Live price for the forming candle (server caches it for 1 s).
  const liveTickQ = useQuery({
    queryKey: ["chart-live-tick", symbol],
    queryFn: () => mt5Api.publicTick(symbol),
    enabled: marketFeedEnabled && Boolean(symbol),
    refetchInterval: 2_000,
    refetchIntervalInBackground: false,
    retry: 0,
    staleTime: 1_000,
  });
  const liveTick = asRecord(asRecord(liveTickQ.data).tick);
  const liveBid = num(liveTick.bid);
  const livePrice = Number.isFinite(liveBid) && liveBid > 0 ? liveBid : lastPrice;

  const feedMeta = asRecord(candlesQ.data);
  const candles = useMemo(
    () => parseCandles(feedMeta.candles ?? candlesQ.data),
    [candlesQ.data, feedMeta.candles],
  );
  const feedStatus = candlesQ.isLoading
    ? "loading"
    : str(feedMeta.status || (candles.length ? "live" : "unavailable"));
  const feedBadge = publicFeedBadge(feedStatus);
  const asOfRaw = str(feedMeta.as_of || "");
  const asOf = (() => {
    if (!asOfRaw) return "";
    const parsed = new Date(asOfRaw);
    if (Number.isNaN(parsed.getTime())) return asOfRaw;
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(parsed);
  })();

  const tfSec = TIMEFRAME_SECONDS[timeframe] ?? 900;
  const offsetRef = useRef(0);
  const fittedKey = useRef("");

  const pushToSeries = (bar: CandlePoint) => {
    const main = mainRef.current;
    if (!main) return;
    if (chartType === "candles") {
      (main as ISeriesApi<"Candlestick">).update({
        time: bar.time,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      });
    } else {
      (main as ISeriesApi<"Line"> | ISeriesApi<"Area">).update({ time: bar.time, value: bar.close });
    }
    volumeRef.current?.update({
      time: bar.time,
      value: bar.volume ?? 0,
      color: bar.close >= bar.open ? "rgba(20, 184, 166, 0.35)" : "rgba(244, 63, 94, 0.35)",
    });
  };

  const setSeriesData = (rows: CandlePoint[]) => {
    const main = mainRef.current;
    if (!main) return;
    if (chartType === "candles") {
      (main as ISeriesApi<"Candlestick">).setData(
        rows.map((c) => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close })),
      );
    } else {
      (main as ISeriesApi<"Line"> | ISeriesApi<"Area">).setData(
        rows.map((c) => ({ time: c.time, value: c.close })),
      );
    }
    volumeRef.current?.setData(
      rows.map((c) => ({
        time: c.time,
        value: c.volume,
        color: c.close >= c.open ? "rgba(20, 184, 166, 0.35)" : "rgba(244, 63, 94, 0.35)",
      })),
    );
    const key = `${symbol}|${timeframe}|${chartType}`;
    if (rows.length && fittedKey.current !== key && chartRef.current) {
      fittedKey.current = key;
      // Show the most recent ~120 bars, right edge at the live candle.
      chartRef.current.timeScale().setVisibleLogicalRange({
        from: Math.max(0, rows.length - 120),
        to: rows.length + 4,
      });
    }
  };

  // Fresh history: keep a newer live-built bar if the feed has not caught up.
  const cacheKeyRef = useRef("");
  useEffect(() => {
    const key = `${symbol}|${timeframe}`;
    const sameSeries = cacheKeyRef.current === key;
    const prev = sameSeries ? candlesCache.current : [];
    const merged = candles.slice();
    const prevLast = prev[prev.length - 1];
    const newLast = merged[merged.length - 1];
    if (prevLast && newLast && prevLast.time > newLast.time && prevLast.time - newLast.time <= tfSec * 3) {
      merged.push(prevLast);
    }
    cacheKeyRef.current = key;
    candlesCache.current = merged;
    if (merged.length) {
      offsetRef.current = clockOffsetSeconds(merged[merged.length - 1].time, Date.now() / 1000, tfSec);
      setOhlc(merged[merged.length - 1]);
    }
    setSeriesData(merged);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles, tfSec, symbol, timeframe]);

  // Live price: move the forming candle, open a new one when its period starts.
  useEffect(() => {
    if (livePrice == null || !Number.isFinite(livePrice)) return;
    if (cacheKeyRef.current !== `${symbol}|${timeframe}`) return;
    const applied = applyLivePrice(
      candlesCache.current,
      livePrice,
      Date.now() / 1000,
      tfSec,
      offsetRef.current,
    );
    if (!applied) return;
    setOhlc(applied.bar as CandlePoint);
    pushToSeries(applied.bar as CandlePoint);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [livePrice, liveTickQ.dataUpdatedAt, tfSec, symbol, timeframe]);

  // Build the chart once per type/volume setting; data flows in above.
  useEffect(() => {
    const el = hostRef.current;
    if (!el) return;
    const chart = createChart(el, {
      autoSize: false,
      width: Math.max(el.clientWidth, 1),
      height: Math.max(el.clientHeight, 1),
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "rgba(226, 232, 240, 0.72)",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(148, 163, 184, 0.06)" },
        horzLines: { color: "rgba(148, 163, 184, 0.06)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false, rightOffset: 4 },
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
        priceLineVisible: true,
        lastValueVisible: true,
      });
    } else if (chartType === "line") {
      main = chart.addSeries(LineSeries, { color: "#00D4E0", lineWidth: 2 });
    } else {
      main = chart.addSeries(AreaSeries, {
        lineColor: "#00D4E0",
        topColor: "rgba(0, 212, 224, 0.28)",
        bottomColor: "rgba(0, 212, 224, 0.02)",
        lineWidth: 2,
      });
    }
    mainRef.current = main;

    if (showVolume) {
      const volume = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
        lastValueVisible: false,
        priceLineVisible: false,
      });
      chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      volumeRef.current = volume;
    }

    fittedKey.current = "";
    setSeriesData(candlesCache.current);

    const fit = () => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      if (w > 0 && h > 0) chart.applyOptions({ width: w, height: h });
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(el);

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
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      mainRef.current = null;
      volumeRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartType, showVolume]);

  return (
    <section
      className="flex h-full min-h-0 flex-col bg-[var(--bg)]"
      aria-label={`${displayTradingSymbol(symbol)} chart workspace`}
    >
      <div
        className={cn(
          "flex min-h-9 min-w-0 shrink-0 items-center gap-2 border-b border-[var(--border)]/70 px-2 py-1",
          comfortable && "flex-col items-stretch gap-1 px-2 py-1.5",
        )}
      >
        <div
          className={cn(
            "flex min-w-0 items-center gap-2",
            !comfortable && "contents",
            comfortable && feedStatus === "live" && "hidden",
          )}
        >
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
            <span className="shrink-0 rounded border border-[var(--border)] px-1.5 py-0.5 text-[9px] font-semibold tracking-wide text-[var(--fg-muted)]">
              {feedBadge.label}
            </span>
          </>
        ) : (
          <span className="shrink-0 rounded border border-[var(--border)] px-1.5 py-0.5 text-[9px] font-semibold tracking-wide text-[var(--fg-muted)]">
            {feedBadge.label}
          </span>
        )}
        {ohlc && !comfortable ? (
          <p
            className="min-w-0 flex-1 truncate tabular text-[10px] text-[var(--fg-muted)]"
            aria-live="polite"
          >
            O {formatNumber(ohlc.open, 2)} · H {formatNumber(ohlc.high, 2)} · L{" "}
            {formatNumber(ohlc.low, 2)} · C {formatNumber(ohlc.close, 2)}
            {asOf ? ` · ${asOf}` : ""}
          </p>
        ) : null}
        </div>
        <div
          className={cn(
            "flex min-w-0 items-center gap-1",
            comfortable ? "flex-wrap" : "ml-auto shrink-0",
          )}
        >
          <div className="flex flex-wrap gap-0.5" role="group" aria-label="Timeframe">
            {TIMEFRAMES.map((tf) => (
              <Button
                key={tf}
                size="sm"
                variant={timeframe === tf ? "secondary" : "ghost"}
                className={comfortable ? "h-6 min-w-[1.6rem] px-1 text-[10px]" : "h-6 min-w-[1.75rem] px-1.5 text-[10px]"}
                data-compact
                onClick={() => onTimeframeChange(tf)}
                aria-pressed={timeframe === tf}
              >
                {tf}
              </Button>
            ))}
          </div>
          <div className={cn("gap-0.5", comfortable ? "flex" : "hidden sm:flex")} role="group" aria-label="Chart type">
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
                className={comfortable ? "h-6 w-6 px-0 text-[10px]" : "h-6 w-6 px-0 text-[10px]"}
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
            className={comfortable ? "h-6 px-1.5 text-[10px]" : "h-6 px-1.5 text-[10px]"}
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

      <div className={cn("relative min-h-[280px] flex-1", comfortable && "min-h-[180px] sm:min-h-[280px]")}>
        {/* The chart host always exists so the chart is built once and data flows in. */}
        <div
          ref={hostRef}
          className={cn(
            "absolute inset-0 min-h-[280px] transition-opacity duration-300",
            comfortable && "min-h-[180px] sm:min-h-[280px]",
            candles.length > 0 ? "opacity-100" : "opacity-0",
          )}
          role="img"
          aria-label={`${displayTradingSymbol(symbol)} price chart`}
        />
        {candles.length > 0 && feedStatus === "closed" ? (
          <div className="pointer-events-none absolute left-3 top-3 z-10 rounded border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg)_88%,transparent)] px-2 py-1 text-[10px] font-medium text-[var(--fg-muted)] backdrop-blur">
            Market closed · last available candles{asOf ? ` · ${asOf}` : ""}
          </div>
        ) : null}
        {candles.length === 0 ? (
          candlesQ.isLoading ? (
            <div className="absolute inset-0 p-4">
              <DeskSkeleton rows={6} />
            </div>
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-6 text-center">
              <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--accent)]" aria-hidden />
              <p className="text-sm text-[var(--fg-muted)]">
                Connecting to the {displayTradingSymbol(symbol)} market feed…
              </p>
              <p className="max-w-sm text-xs text-[var(--fg-subtle)]">
                {candlesQ.isError
                  ? candleLoadErrorMessage(candlesQ.error, symbol, session?.gatewayOnline ?? null)
                  : "Retrying automatically."}
              </p>
            </div>
          )
        ) : null}
      </div>
    </section>
  );
});
