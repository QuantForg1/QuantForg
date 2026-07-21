"use client";

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
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { mt5Api } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn, formatNumber } from "@/lib/utils";
import { Cable } from "lucide-react";

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
  // Deduplicate identical timestamps (lightweight-charts requires unique ascending times)
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
  timeframe,
  onTimeframeChange,
  chartType,
  onChartTypeChange,
  showVolume,
  onShowVolumeChange,
  fullscreen,
  onFullscreenChange,
  lastPrice,
}: {
  symbol: string;
  connected: boolean;
  timeframe: string;
  onTimeframeChange: (tf: string) => void;
  chartType: ChartType;
  onChartTypeChange: (t: ChartType) => void;
  showVolume: boolean;
  onShowVolumeChange: (v: boolean) => void;
  fullscreen: boolean;
  onFullscreenChange: (v: boolean) => void;
  lastPrice?: number;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const mainRef = useRef<ISeriesApi<"Candlestick"> | ISeriesApi<"Line"> | ISeriesApi<"Area"> | null>(
    null,
  );
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const [ohlc, setOhlc] = useState<CandlePoint | null>(null);
  const candlesCache = useRef<CandlePoint[]>([]);

  const candlesQ = useQuery({
    queryKey: ["mt5-candles", symbol, timeframe],
    queryFn: () => mt5Api.candles(symbol, timeframe, 400),
    retry: false,
    enabled: connected && Boolean(symbol),
    staleTime: 60_000,
  });

  const candles = useMemo(() => parseCandles(candlesQ.data), [candlesQ.data]);

  useEffect(() => {
    candlesCache.current = candles;
    if (candles.length) setOhlc(candles[candles.length - 1]);
  }, [candles]);

  // Live last-price update on the forming candle (no candle polling)
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
        textColor: "rgba(160, 170, 185, 1)",
        fontFamily: "inherit",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.04)" },
        horzLines: { color: "rgba(255,255,255,0.04)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
    });
    chartRef.current = chart;

    const applySeries = () => {
      if (mainRef.current) {
        chart.removeSeries(mainRef.current);
        mainRef.current = null;
      }
      if (volumeRef.current) {
        chart.removeSeries(volumeRef.current);
        volumeRef.current = null;
      }

      const data = candlesCache.current;
      if (chartType === "candles") {
        const s = chart.addSeries(CandlestickSeries, {
          upColor: "#2f9e7a",
          downColor: "#d45d5d",
          borderVisible: false,
          wickUpColor: "#2f9e7a",
          wickDownColor: "#d45d5d",
        });
        s.setData(
          data.map((c) => ({
            time: c.time,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          })),
        );
        mainRef.current = s;
      } else if (chartType === "line") {
        const s = chart.addSeries(LineSeries, {
          color: "#6b8cff",
          lineWidth: 2,
        });
        s.setData(data.map((c) => ({ time: c.time, value: c.close })));
        mainRef.current = s;
      } else {
        const s = chart.addSeries(AreaSeries, {
          lineColor: "#6b8cff",
          topColor: "rgba(107, 140, 255, 0.22)",
          bottomColor: "rgba(107, 140, 255, 0.02)",
          lineWidth: 2,
        });
        s.setData(data.map((c) => ({ time: c.time, value: c.close })));
        mainRef.current = s;
      }

      if (showVolume) {
        const v = chart.addSeries(HistogramSeries, {
          priceFormat: { type: "volume" },
          priceScaleId: "volume",
        });
        chart.priceScale("volume").applyOptions({
          scaleMargins: { top: 0.82, bottom: 0 },
        });
        v.setData(
          data.map((c) => ({
            time: c.time,
            value: c.volume,
            color:
              c.close >= c.open ? "rgba(47,158,122,0.4)" : "rgba(212,93,93,0.4)",
          })),
        );
        volumeRef.current = v;
      }

      chart.timeScale().fitContent();
    };

    applySeries();

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
      aria-label={`${symbol} chart workspace`}
    >
      <div className="flex h-8 shrink-0 items-center gap-1.5 border-b border-[var(--border)]/70 px-2">
        <p className="text-xs font-semibold tracking-tight text-[var(--fg)]">{symbol}</p>
        <span
          className={cn(
            "qf-status-dot",
          )}
          data-state={connected ? "ok" : "warn"}
          aria-label={connected ? "Live" : "Offline"}
        />
        {ohlc ? (
          <p className="hidden tabular text-[10px] text-[var(--fg-muted)] md:inline" aria-live="polite">
            O {formatNumber(ohlc.open, 2)} · H {formatNumber(ohlc.high, 2)} · L{" "}
            {formatNumber(ohlc.low, 2)} · C {formatNumber(ohlc.close, 2)}
          </p>
        ) : (
          <span className="inline-block h-3 w-40" aria-hidden />
        )}
        <div className="ml-auto flex flex-wrap items-center gap-0.5">
          <div className="flex gap-0.5" role="group" aria-label="Timeframe">
            {TIMEFRAMES.map((tf) => (
              <Button
                key={tf}
                size="sm"
                variant={timeframe === tf ? "secondary" : "ghost"}
                className="h-6 min-w-[1.75rem] px-1.5 text-[10px]"
                data-compact
                onClick={() => onTimeframeChange(tf)}
                disabled={!connected}
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

      <div className="relative min-h-0 flex-1">
        {!connected ? (
          <div className="absolute inset-0 flex items-center justify-center p-6">
            <DeskEmpty
              icon={Cable}
              title="Broker disconnected"
              description="Connect MT5 to load candles from the production market data API."
              actionLabel="Connect MT5"
              actionHref="/broker"
            />
          </div>
        ) : candlesQ.isLoading ? (
          <div className="p-4">
            <DeskSkeleton rows={6} />
          </div>
        ) : candlesQ.isError ? (
          <div className="p-4">
            <DeskError
              message="Unable to load candles from MT5."
              onRetry={() => candlesQ.refetch()}
            />
          </div>
        ) : candles.length === 0 ? (
          <div className="flex h-full items-center justify-center p-6 text-sm text-[var(--fg-muted)]">
            No candle history returned for {symbol} ({timeframe}).
          </div>
        ) : (
          <div ref={hostRef} className="absolute inset-0" role="img" aria-label={`${symbol} price chart`} />
        )}
      </div>
    </section>
  );
});
