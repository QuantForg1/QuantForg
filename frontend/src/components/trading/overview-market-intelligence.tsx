"use client";

import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Clock, Gauge, MoveDown, MoveUp } from "lucide-react";
import { mt5Api } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { DeskSkeleton } from "@/components/desk/primitives";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import {
  classifyDirection,
  classifyMomentum,
  classifyRegime,
  confirmedCandles,
  feedFreshness,
  swingLevels,
  tradingSessionLabel,
  type DisplayCandle,
} from "@/lib/market/display-intelligence";
import { cn } from "@/lib/utils";

function parseCandles(raw: unknown): DisplayCandle[] {
  const rows = asList(raw).map(asRecord);
  const points: DisplayCandle[] = [];
  for (const row of rows) {
    const time = Date.parse(str(row.open_time));
    if (!Number.isFinite(time)) continue;
    const open = num(row.open);
    const high = num(row.high);
    const low = num(row.low);
    const close = num(row.close);
    if (![open, high, low, close].every(Number.isFinite)) continue;
    points.push({ time: Math.floor(time / 1000), open, high, low, close });
  }
  points.sort((a, b) => a.time - b.time);
  return points;
}

function numericLevel(value: string): number | null {
  if (!value || value === "—" || /not available|unavailable/i.test(value)) return null;
  const parsed = Number(value.replace(/[$,\s]/g, ""));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function formatPx(value: number): string {
  return value.toFixed(2);
}

const ROW_ICONS: Record<string, ComponentType<{ className?: string }>> = {
  Support: MoveDown,
  Resistance: MoveUp,
  Regime: Activity,
  Momentum: Gauge,
  Session: Clock,
};

function formatStamp(raw: string, updatedAtMs?: number): string {
  const parsed = raw ? new Date(raw) : updatedAtMs ? new Date(updatedAtMs) : null;
  if (!parsed || Number.isNaN(parsed.getTime())) return "";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

export function OverviewMarketIntelligence({
  timeframe,
  lastPrice,
  marketFeedStatus,
  tickUpdatedAt,
  tickTime,
  tickLoading,
  tickError,
  support,
  resistance,
  confidencePct,
  signalDirection,
}: {
  timeframe: string;
  lastPrice?: number;
  marketFeedStatus?: string;
  tickUpdatedAt?: number;
  tickTime?: string;
  tickLoading?: boolean;
  tickError?: boolean;
  support: string;
  resistance: string;
  confidencePct: number | null;
  signalDirection: "BUY" | "SELL" | "WAIT";
}) {
  const [now, setNow] = useState(() => new Date());
  const [flash, setFlash] = useState<"up" | "down" | null>(null);
  const previousPrice = useRef<number | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (lastPrice == null || !Number.isFinite(lastPrice)) return;
    const prior = previousPrice.current;
    previousPrice.current = lastPrice;
    if (prior == null || prior === lastPrice) return;
    setFlash(lastPrice > prior ? "up" : "down");
    const timer = window.setTimeout(() => setFlash(null), 700);
    return () => window.clearTimeout(timer);
  }, [lastPrice]);

  const candlesQ = useQuery({
    queryKey: ["public-market-candles", TRADING_SYMBOL, timeframe],
    queryFn: async () => {
      try {
        return await mt5Api.publicCandles(TRADING_SYMBOL, timeframe, 400);
      } catch {
        const rows = await mt5Api.researchCandles(TRADING_SYMBOL, timeframe, 400);
        return {
          ok: true,
          status: "live",
          source: "mt5_research",
          as_of: null,
          candles: rows,
        };
      }
    },
    retry: 1,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });

  const feedMeta = asRecord(candlesQ.data);
  const candles = useMemo(
    () => parseCandles(feedMeta.candles ?? candlesQ.data),
    [candlesQ.data, feedMeta.candles],
  );
  const confirmed = useMemo(
    () => confirmedCandles(candles, timeframe, Math.floor(now.getTime() / 1000)),
    [candles, timeframe, now],
  );
  const hasPrice = lastPrice != null && Number.isFinite(lastPrice);
  const referencePrice = hasPrice ? lastPrice : confirmed.at(-1)?.close;
  const researchSupport = numericLevel(support);
  const researchResistance = numericLevel(resistance);
  const swings =
    referencePrice != null ? swingLevels(confirmed, referencePrice) : { support: [], resistance: [] };
  const supportLevels = researchSupport != null ? [researchSupport] : swings.support;
  const resistanceLevels = researchResistance != null ? [researchResistance] : swings.resistance;
  const supportContext = researchSupport != null ? "Research" : `${timeframe} swing`;
  const resistanceContext = researchResistance != null ? "Research" : `${timeframe} swing`;
  const regime = classifyRegime(confirmed);
  const momentum = classifyMomentum(confirmed);
  const direction = classifyDirection(
    confirmed,
    signalDirection === "WAIT" ? "WAIT" : signalDirection,
  );
  const freshness = feedFreshness({
    loading: Boolean(tickLoading),
    error: Boolean(tickError),
    hasPrice,
    status: marketFeedStatus || "",
    updatedAtMs: tickUpdatedAt ?? null,
    nowMs: now.getTime(),
  });
  const stamp = formatStamp(tickTime || "", tickUpdatedAt);
  const showCandleGap = candlesQ.isError && supportLevels.length === 0 && resistanceLevels.length === 0 && !regime;

  const rows: Array<[string, string, string]> = [];
  if (supportLevels.length) {
    rows.push(["Support", supportLevels.map(formatPx).join(" · "), supportContext]);
  }
  if (resistanceLevels.length) {
    rows.push(["Resistance", resistanceLevels.map(formatPx).join(" · "), resistanceContext]);
  }
  if (regime) rows.push(["Regime", regime, `Closed ${timeframe}`]);
  if (momentum) rows.push(["Momentum", momentum, `Closed ${timeframe}`]);
  rows.push(["Session", tradingSessionLabel(now), "UTC"]);

  const directionTone =
    direction === "Bullish" ? "text-[var(--success)]" : direction === "Bearish" ? "text-[var(--danger)]" : "text-[var(--fg)]";

  if (tickLoading && !hasPrice && candlesQ.isLoading) {
    return <DeskSkeleton rows={4} />;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Gold market
            </p>
            {direction ? (
              <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", directionTone, direction === "Bullish" ? "bg-[var(--success-soft)]" : direction === "Bearish" ? "bg-[var(--danger-soft)]" : "bg-[var(--surface-2)]")}>
                {direction}
              </span>
            ) : null}
          </div>
          {hasPrice ? (
            <p
              className={cn(
                "mt-1 font-mono text-2xl font-semibold tabular tracking-tight text-[var(--fg)] transition-colors duration-200 sm:text-3xl",
                flash === "up" && "text-[var(--success)]",
                flash === "down" && "text-[var(--danger)]",
              )}
            >
              {formatPx(lastPrice)}
            </p>
          ) : null}
          {stamp ? <p className="text-[11px] text-[var(--fg-subtle)]">{stamp}</p> : null}
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.08em]",
            freshness.tone === "fresh" && "bg-[var(--success-soft)] text-[var(--success)]",
            freshness.tone === "warn" && "bg-[var(--warning-soft)] text-[var(--warning)]",
            freshness.tone === "stale" && "bg-[var(--warning-soft)] text-[var(--warning)]",
            freshness.tone === "down" && "bg-[var(--danger-soft)] text-[var(--danger)]",
          )}
        >
          {freshness.label}
        </span>
      </div>

      {showCandleGap ? (
        <p className="text-xs text-[var(--fg-muted)]">
          Candle history is not available, so support, resistance, and regime stay hidden.
        </p>
      ) : null}

      <dl className="divide-y divide-[color-mix(in_srgb,var(--accent)_14%,var(--border))]">
        {rows.map(([label, value, context]) => {
          const Icon = ROW_ICONS[label] ?? Activity;
          return (
            <div key={label} className="flex items-center justify-between gap-3 py-2.5">
              <dt className="flex min-w-0 items-center gap-2 text-xs text-[var(--fg-muted)]">
                <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" aria-hidden />
                <span>{label}</span>
              </dt>
              <dd className="min-w-0 text-right">
                <span className="font-mono text-sm font-medium tabular text-[var(--fg)]">{value}</span>
                <span className="mt-0.5 block text-[10px] uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
                  {context}
                </span>
              </dd>
            </div>
          );
        })}
      </dl>

      {confidencePct != null ? (
        <div>
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Signal confidence
            </p>
            <p className="font-mono text-sm tabular">{confidencePct}%</p>
          </div>
          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-[var(--surface-2)]" aria-hidden>
            <div
              className="h-full rounded-full bg-[var(--accent)]"
              style={{ width: `${Math.max(0, Math.min(100, confidencePct))}%` }}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
