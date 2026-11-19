"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  ExternalLink,
  MinusCircle,
  Sparkles,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError } from "@/components/desk/primitives";
import { intelligenceApi, strategyLabApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import {
  biasTone,
  formatCountdown,
  formatPrice,
  formatUtcTime,
  impactTone,
  minutesUntil,
  regimeLabels,
  relativeTime,
  strategyFit,
} from "@/lib/assistant/desk-format";
import { cn } from "@/lib/utils";

type Ask = (prompt: string) => void;

export const DESK_QUERY_KEY = ["intelligence-desk"] as const;

export function useMarketDesk(enabled = true) {
  return useQuery({
    queryKey: DESK_QUERY_KEY,
    queryFn: () => intelligenceApi.desk(),
    retry: 1,
    staleTime: 10_000,
    refetchInterval: enabled ? 20_000 : false,
    enabled,
  });
}

/* ------------------------------------------------------------- primitives */

function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <section
      className={cn(
        "rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] p-4",
        className,
      )}
    >
      {children}
    </section>
  );
}

function Label({ children }: { children: ReactNode }) {
  return (
    <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
      {children}
    </p>
  );
}

function AskButton({ onAsk, prompt, children }: { onAsk: Ask; prompt: string; children: ReactNode }) {
  return (
    <Button type="button" size="sm" variant="secondary" onClick={() => onAsk(prompt)}>
      <Sparkles className="h-3.5 w-3.5" />
      {children}
    </Button>
  );
}

function Loading({ label }: { label: string }) {
  return (
    <div className="mx-auto grid w-full max-w-5xl gap-3 sm:grid-cols-3" aria-busy="true" aria-label={label}>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-24 animate-pulse rounded-[var(--radius-os)] bg-[var(--surface-2)]" />
      ))}
    </div>
  );
}

function UpdatedAt({ iso }: { iso: string }) {
  if (!iso) return null;
  return (
    <span className="inline-flex items-center gap-1 text-xs text-[var(--fg-subtle)]">
      <Clock className="h-3 w-3" /> Updated {formatUtcTime(iso)}
    </span>
  );
}

function TrendIcon({ trend, className }: { trend: string; className?: string }) {
  if (trend.startsWith("up")) return <ArrowUpRight className={cn("text-[var(--success)]", className)} />;
  if (trend.startsWith("down")) return <ArrowDownRight className={cn("text-[var(--danger)]", className)} />;
  return <ArrowRight className={cn("text-[var(--fg-muted)]", className)} />;
}

function trendWord(trend: string): string {
  if (trend.startsWith("up")) return "Uptrend";
  if (trend.startsWith("down")) return "Downtrend";
  if (trend.startsWith("mixed")) return "Ranging";
  return "Unclear";
}

function RsiMeter({ value }: { value: number }) {
  const v = Math.max(0, Math.min(100, value));
  const tone = v >= 70 ? "var(--warning)" : v <= 30 ? "var(--warning)" : "var(--accent)";
  return (
    <div className="relative mt-1 h-1.5 w-full rounded-full bg-[var(--border)]" aria-hidden>
      <span className="absolute inset-y-0 left-[30%] w-px bg-[var(--fg-subtle)]" />
      <span className="absolute inset-y-0 left-[70%] w-px bg-[var(--fg-subtle)]" />
      <span className="absolute -top-0.5 h-2.5 w-2.5 -translate-x-1/2 rounded-full" style={{ left: `${v}%`, background: tone }} />
    </div>
  );
}

function Sparkline({ closes }: { closes: number[] }) {
  if (closes.length < 2) return null;
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = max - min || 1;
  const pts = closes
    .map((c, i) => `${(i / (closes.length - 1)) * 100},${30 - ((c - min) / span) * 28 - 1}`)
    .join(" ");
  const up = closes[closes.length - 1] >= closes[0];
  return (
    <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="h-10 w-full" aria-hidden>
      <polyline
        points={pts}
        fill="none"
        stroke={up ? "var(--success)" : "var(--danger)"}
        strokeWidth="1.6"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

/* --------------------------------------------------------- Market Insights */

export function InsightsDesk({ onAsk }: { onAsk: Ask }) {
  const q = useMarketDesk();
  if (q.isLoading) return <Loading label="Loading live market" />;
  if (q.isError) return <DeskError message="Live market data could not be loaded." onRetry={() => q.refetch()} />;

  const snap = asRecord(asRecord(q.data).snapshot);
  const quote = asRecord(snap.quote);
  const bias = asRecord(snap.bias);
  const vol = asRecord(snap.volatility_h1);
  const tfs = asList(snap.timeframes).map(asRecord);
  const h1 = tfs.find((t) => t.timeframe === "H1") ?? {};
  const bid = num(quote.bid);
  const ask = num(quote.ask);
  const mid = Number.isFinite(bid) && Number.isFinite(ask) ? (bid + ask) / 2 : num(h1.last_close);
  const levels = asRecord(snap.key_levels_h1);
  const res = asList(levels.resistances).map(Number).filter(Number.isFinite);
  const sup = asList(levels.supports).map(Number).filter(Number.isFinite);
  const atrH1 = num(h1.atr14);
  const direction = str(bias.direction, "unknown");
  const m15 = tfs.find((t) => t.timeframe === "M15") ?? {};
  const spark = asList(m15.recent_bars).map((b) => num(asRecord(b).c)).filter(Number.isFinite);
  const change = num(h1.change_last_20_bars_pct);

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      <Card className="grid gap-4 md:grid-cols-[1.2fr_1fr]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Label>XAUUSD · Gold spot</Label>
            <Badge tone={biasTone(direction)}>
              {direction === "unknown" ? "Bias unavailable" : `${direction[0].toUpperCase()}${direction.slice(1)} ${num(bias.aligned)}/${num(bias.of)} timeframes`}
            </Badge>
          </div>
          <p className="mt-2 text-4xl font-semibold tracking-tight tabular-nums">
            {Number.isFinite(mid) ? formatPrice(mid) : "—"}
          </p>
          <p className="mt-1 text-sm tabular-nums text-[var(--fg-muted)]">
            Bid {formatPrice(bid)} · Ask {formatPrice(ask)} · Spread {formatPrice(num(quote.spread))}
            {Number.isFinite(change) ? (
              <span className={change >= 0 ? " text-[var(--success)]" : " text-[var(--danger)]"}>
                {" "}
                · {change >= 0 ? "+" : ""}
                {change.toFixed(2)}% (20 H1 bars)
              </span>
            ) : null}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Badge tone="neutral">{str(snap.session, "Session —")}</Badge>
            <Badge tone={str(vol.state) === "high" ? "warning" : "neutral"}>
              Volatility {str(vol.state, "—")}
              {vol.atr_vs_average != null ? ` (${num(vol.atr_vs_average)}×)` : ""}
            </Badge>
            <UpdatedAt iso={str(snap.generated_at_utc, "")} />
          </div>
        </div>
        <div className="flex flex-col justify-between gap-2">
          <Label>M15 · last 12 candles</Label>
          <Sparkline closes={spark} />
          <AskButton onAsk={onAsk} prompt="Explain the current XAUUSD market: trend on each timeframe, key support and resistance, momentum, and what to watch next.">
            Explain this market
          </AskButton>
        </div>
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">
        {tfs.map((tf) => {
          const tfName = str(tf.timeframe);
          if (!tf.available) {
            return (
              <Card key={tfName}>
                <Label>{tfName}</Label>
                <p className="mt-2 text-sm text-[var(--fg-muted)]">Not available right now.</p>
              </Card>
            );
          }
          const trend = str(tf.trend, "");
          const rsiV = num(tf.rsi14);
          const price = num(tf.last_close);
          const e20 = num(tf.ema20);
          const e50 = num(tf.ema50);
          return (
            <Card key={tfName}>
              <div className="flex items-center justify-between">
                <Label>{tfName}</Label>
                <span className="inline-flex items-center gap-1 text-sm font-semibold">
                  <TrendIcon trend={trend} className="h-4 w-4" />
                  {trendWord(trend)}
                </span>
              </div>
              <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-sm tabular-nums">
                <div>
                  <dt className="text-xs text-[var(--fg-subtle)]">RSI 14</dt>
                  <dd className="font-medium">{Number.isFinite(rsiV) ? rsiV.toFixed(1) : "—"}</dd>
                  {Number.isFinite(rsiV) ? <RsiMeter value={rsiV} /> : null}
                </div>
                <div>
                  <dt className="text-xs text-[var(--fg-subtle)]">ATR 14</dt>
                  <dd className="font-medium">{formatPrice(num(tf.atr14))}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--fg-subtle)]">EMA 20</dt>
                  <dd className={cn("font-medium", price > e20 ? "text-[var(--success)]" : "text-[var(--danger)]")}>
                    {formatPrice(e20)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--fg-subtle)]">EMA 50</dt>
                  <dd className={cn("font-medium", price > e50 ? "text-[var(--success)]" : "text-[var(--danger)]")}>
                    {formatPrice(e50)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--fg-subtle)]">20-bar high</dt>
                  <dd className="font-medium">{formatPrice(num(tf.high_last_20))}</dd>
                </div>
                <div>
                  <dt className="text-xs text-[var(--fg-subtle)]">20-bar low</dt>
                  <dd className="font-medium">{formatPrice(num(tf.low_last_20))}</dd>
                </div>
              </dl>
            </Card>
          );
        })}
      </div>

      <Card>
        <div className="flex items-center justify-between">
          <Label>Key levels · H1 swing highs and lows</Label>
          {Number.isFinite(atrH1) ? (
            <span className="text-xs text-[var(--fg-subtle)]">Distance in $ and H1 ATR ({formatPrice(atrH1)})</span>
          ) : null}
        </div>
        {res.length === 0 && sup.length === 0 ? (
          <p className="mt-3 text-sm text-[var(--fg-muted)]">No clear swing levels in the recent data.</p>
        ) : (
          <ul className="mt-3 divide-y divide-[var(--border)] text-sm tabular-nums">
            {[...res].reverse().map((lv) => (
              <LevelRow key={`r${lv}`} kind="Resistance" level={lv} price={mid} atr={atrH1} />
            ))}
            <li className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 rounded-md bg-[color-mix(in_srgb,var(--accent)_12%,transparent)] px-2 py-2 font-semibold">
              <span className="text-[var(--accent)]">Price now</span>
              <span className="text-center">{formatPrice(mid)}</span>
              <span />
            </li>
            {sup.map((lv) => (
              <LevelRow key={`s${lv}`} kind="Support" level={lv} price={mid} atr={atrH1} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function LevelRow({ kind, level, price, atr }: { kind: "Support" | "Resistance"; level: number; price: number; atr: number }) {
  const dist = Math.abs(level - price);
  return (
    <li className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 px-2 py-2">
      <span className={kind === "Resistance" ? "text-[var(--danger)]" : "text-[var(--success)]"}>{kind}</span>
      <span className="text-center font-medium">{formatPrice(level)}</span>
      <span className="text-right text-xs text-[var(--fg-muted)]">
        {Number.isFinite(price) ? `${dist.toFixed(2)} away` : ""}
        {Number.isFinite(atr) && atr > 0 && Number.isFinite(price) ? ` · ${(dist / atr).toFixed(1)}× ATR` : ""}
      </span>
    </li>
  );
}

/* ----------------------------------------------------------- Trade Analysis */

const STATUS_ICON = {
  good: <CheckCircle2 className="h-4 w-4 text-[var(--success)]" />,
  caution: <AlertTriangle className="h-4 w-4 text-[var(--warning)]" />,
  avoid: <XCircle className="h-4 w-4 text-[var(--danger)]" />,
} as const;

export function AnalysisDesk({ onAsk }: { onAsk: Ask }) {
  const q = useMarketDesk();
  const dash = useQuery({
    queryKey: ["intelligence-dashboard"],
    queryFn: () => intelligenceApi.dashboard("FX"),
    retry: false,
    refetchInterval: 45_000,
    staleTime: 12_000,
  });
  if (q.isLoading) return <Loading label="Evaluating conditions" />;
  if (q.isError) return <DeskError message="Trade conditions could not be evaluated." onRetry={() => q.refetch()} />;

  const data = asRecord(q.data);
  const cond = asRecord(data.conditions);
  const snap = asRecord(data.snapshot);
  const items = asList(cond.items).map(asRecord);
  const tone = str(cond.tone, "caution");
  const score = num(cond.score);
  const bias = str(cond.bias, "unknown");
  const positions = asList(asRecord(dash.data).positions).map(asRecord);
  const pending = asList(asRecord(dash.data).pending_orders).map(asRecord);
  const toneColor = tone === "good" ? "var(--success)" : tone === "avoid" ? "var(--danger)" : "var(--warning)";

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      <Card className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <ScoreRing score={score} color={toneColor} />
        <div className="min-w-0 flex-1">
          <Label>Trading conditions now</Label>
          <p className="mt-1 text-xl font-semibold" style={{ color: toneColor }}>
            {str(cond.verdict, "Unavailable")}
          </p>
          <p className="mt-1 text-sm text-[var(--fg-muted)]">
            Market bias: <span className="font-medium text-[var(--fg)]">{bias}</span>. This reads conditions, it is not a
            buy or sell signal.
          </p>
          <div className="mt-2">
            <UpdatedAt iso={str(snap.generated_at_utc, "")} />
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <AskButton
            onAsk={onAsk}
            prompt="Build a complete XAUUSD trade plan for right now using the live data: bias, entry zone, stop loss, two take-profit targets, reward-to-risk, position-size guidance for my risk settings, and what would invalidate the plan."
          >
            Get a full trade plan
          </AskButton>
          <AskButton onAsk={onAsk} prompt="Explain each trading-conditions check for XAUUSD right now and what would need to change for conditions to improve.">
            Explain the checks
          </AskButton>
        </div>
      </Card>

      <Card>
        <Label>Checklist</Label>
        <ul className="mt-2 divide-y divide-[var(--border)]">
          {items.map((it) => {
            const status = str(it.status, "caution") as keyof typeof STATUS_ICON;
            return (
              <li key={str(it.key)} className="flex items-start gap-3 py-2.5">
                <span className="mt-0.5">{STATUS_ICON[status] ?? <MinusCircle className="h-4 w-4" />}</span>
                <div className="min-w-0">
                  <p className="text-sm font-medium">{str(it.label)}</p>
                  <p className="text-sm text-[var(--fg-muted)]">{str(it.detail)}</p>
                </div>
              </li>
            );
          })}
        </ul>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <Label>Your open positions</Label>
          {dash.isError ? <span className="text-xs text-[var(--fg-subtle)]">Broker data unavailable</span> : null}
        </div>
        {positions.length === 0 && pending.length === 0 ? (
          <p className="mt-2 text-sm text-[var(--fg-muted)]">
            {dash.isLoading ? "Loading positions…" : "No open positions or pending orders."}
          </p>
        ) : (
          <ul className="mt-2 divide-y divide-[var(--border)] text-sm">
            {[...positions, ...pending].slice(0, 10).map((row, i) => {
              const pnl = num(row.profit);
              const isPos = i < positions.length;
              return (
                <li key={`${str(row.ticket, String(i))}`} className="flex items-center justify-between gap-3 py-2">
                  <span className="min-w-0 truncate font-medium">
                    {str(row.symbol, "—")} · {str(isPos ? row.side : row.order_type, "—")} · {str(row.volume, "—")} lot
                  </span>
                  <span className="shrink-0 tabular-nums text-[var(--fg-muted)]">
                    {str(row.price_open || row.price, "")}
                    {isPos && Number.isFinite(pnl) ? (
                      <span className={pnl >= 0 ? " text-[var(--success)]" : " text-[var(--danger)]"}>
                        {" "}
                        {pnl >= 0 ? "+" : ""}
                        {pnl.toFixed(2)}
                      </span>
                    ) : null}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}

function ScoreRing({ score, color }: { score: number; color: string }) {
  const v = Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 0;
  const r = 34;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative h-20 w-20 shrink-0" role="img" aria-label={`Conditions score ${Number.isFinite(score) ? score : "unavailable"}`}>
      <svg viewBox="0 0 80 80" className="h-full w-full -rotate-90">
        <circle cx="40" cy="40" r={r} fill="none" stroke="var(--border)" strokeWidth="7" />
        <circle
          cx="40"
          cy="40"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={`${(v / 100) * c} ${c}`}
        />
      </svg>
      <span className="absolute inset-0 grid place-items-center text-xl font-semibold tabular-nums">
        {Number.isFinite(score) ? score : "—"}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------- Strategy Lab */

export function StrategyDesk({ onAsk }: { onAsk: Ask }) {
  const desk = useMarketDesk();
  const registryQ = useQuery({
    queryKey: ["strategy-lab-registry"],
    queryFn: () => strategyLabApi.registry(),
    retry: false,
    staleTime: 60_000,
  });
  if (registryQ.isLoading) return <Loading label="Loading strategies" />;
  if (registryQ.isError) return <DeskError message="Strategy Lab could not be loaded." onRetry={() => registryQ.refetch()} />;

  const snap = asRecord(asRecord(desk.data).snapshot);
  const regimes = regimeLabels(asRecord(snap.bias), asRecord(snap.volatility_h1));
  const strategies = asList(asRecord(registryQ.data).strategies)
    .map(asRecord)
    .map((s) => ({ s, fit: strategyFit(asList(s.best_regimes).map(String), regimes) }))
    .sort((a, b) => b.fit - a.fit || str(a.s.name).localeCompare(str(b.s.name)));

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      <Card className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Label>Current gold regime</Label>
          <div className="mt-2 flex flex-wrap gap-2">
            {regimes.length ? (
              regimes.map((r) => (
                <Badge key={r} tone="accent">
                  {r}
                </Badge>
              ))
            ) : (
              <span className="text-sm text-[var(--fg-muted)]">Regime unavailable</span>
            )}
          </div>
        </div>
        <p className="max-w-md text-xs leading-relaxed text-[var(--fg-subtle)]">
          Strategies are ranked by how well their best conditions match the live market. Research only: the robot does
          not switch strategies from this list.
        </p>
      </Card>
      <div className="grid gap-3 md:grid-cols-2">
        {strategies.map(({ s, fit }) => (
          <Card key={str(s.key)} className="flex flex-col gap-2">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">{str(s.name) || str(s.key)}</p>
                <p className="text-xs capitalize text-[var(--fg-subtle)]">{str(s.family).replace(/_/g, " ")}</p>
              </div>
              {fit > 0 ? <Badge tone="success">Fits now</Badge> : <Badge tone="neutral">Not ideal now</Badge>}
            </div>
            <p className="text-sm leading-relaxed text-[var(--fg-muted)]">{str(s.description)}</p>
            <div className="flex flex-wrap gap-1.5">
              {asList(s.best_regimes).map((r) => (
                <span
                  key={String(r)}
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-[11px]",
                    regimes.includes(String(r))
                      ? "border-[var(--success)] text-[var(--success)]"
                      : "border-[var(--border)] text-[var(--fg-subtle)]",
                  )}
                >
                  {String(r)}
                </span>
              ))}
            </div>
            <div className="mt-auto flex items-center justify-between pt-1">
              <span className="text-[11px] text-[var(--fg-subtle)]">
                {s.engine_plugin ? "Backtestable engine plugin" : "Research archetype"}
              </span>
              <button
                type="button"
                className="text-xs font-medium text-[var(--accent)] hover:underline"
                onClick={() =>
                  onAsk(`Explain the ${str(s.name)} strategy for gold: how it works, entry and exit rules, and whether it suits the current XAUUSD market.`)
                }
              >
                Ask AI about it →
              </button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- Market News */

function useNow(intervalMs = 30_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(t);
  }, [intervalMs]);
  return now;
}

export function NewsDesk({ onAsk }: { onAsk: Ask }) {
  const now = useNow();
  const newsQ = useQuery({
    queryKey: ["intelligence-news"],
    queryFn: () => intelligenceApi.news(20),
    retry: false,
    staleTime: 60_000,
    refetchInterval: 120_000,
  });
  const calendarQ = useQuery({
    queryKey: ["intelligence-calendar"],
    queryFn: () => intelligenceApi.calendar(30),
    retry: false,
    staleTime: 60_000,
    refetchInterval: 120_000,
  });
  if (newsQ.isLoading || calendarQ.isLoading) return <Loading label="Loading news" />;
  if (newsQ.isError && calendarQ.isError) {
    return (
      <DeskError
        message="The news and economic-calendar feeds could not be loaded."
        onRetry={() => {
          void newsQ.refetch();
          void calendarQ.refetch();
        }}
      />
    );
  }
  const headlines = asList(newsQ.isError ? [] : newsQ.data).map(asRecord).filter((i) => str(i.title, ""));
  const events = asList(calendarQ.isError ? [] : calendarQ.data)
    .map(asRecord)
    .filter((e) => str(e.title, ""))
    .sort((a, b) => Date.parse(str(a.scheduled_at)) - Date.parse(str(b.scheduled_at)));
  const upcoming = events.filter((e) => minutesUntil(str(e.scheduled_at), now) >= -30);
  const nextHigh = upcoming.find((e) => impactTone(str(e.impact)) === "danger" && minutesUntil(str(e.scheduled_at), now) >= 0);

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      {nextHigh ? (
        <Card className="flex flex-wrap items-center justify-between gap-3 border-[color-mix(in_srgb,var(--danger)_45%,var(--border))]">
          <div>
            <Label>Next high-impact event</Label>
            <p className="mt-1 text-lg font-semibold">{str(nextHigh.title)}</p>
            <p className="text-sm text-[var(--fg-muted)]">
              {str(nextHigh.country)} ·{" "}
              {new Date(str(nextHigh.scheduled_at)).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" })}{" "}
              · in{" "}
              {formatCountdown(minutesUntil(str(nextHigh.scheduled_at), now))}
            </p>
          </div>
          <AskButton onAsk={onAsk} prompt={`How could "${str(nextHigh.title)}" move gold (XAUUSD)? Explain the likely reaction if it comes in above or below forecast, and how to manage risk around it.`}>
            How could this move gold?
          </AskButton>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <div className="flex items-center justify-between">
            <Label>Economic calendar</Label>
            {calendarQ.isError ? <span className="text-xs text-[var(--fg-subtle)]">Unavailable</span> : null}
          </div>
          {upcoming.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--fg-muted)]">No upcoming events from the calendar feed.</p>
          ) : (
            <ul className="mt-2 divide-y divide-[var(--border)]">
              {upcoming.slice(0, 14).map((e, i) => {
                const mins = minutesUntil(str(e.scheduled_at), now);
                return (
                  <li key={`${str(e.title)}-${i}`} className="flex items-start justify-between gap-3 py-2.5">
                    <div className="min-w-0">
                      <p className="text-sm font-medium leading-snug">{str(e.title)}</p>
                      <p className="mt-0.5 text-xs text-[var(--fg-muted)]">
                        {str(e.country)} · {new Date(str(e.scheduled_at)).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" })}
                        {str(e.forecast, "") ? ` · F ${str(e.forecast)}` : ""}
                        {str(e.previous, "") ? ` · P ${str(e.previous)}` : ""}
                        {str(e.actual, "") ? ` · A ${str(e.actual)}` : ""}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <Badge tone={impactTone(str(e.impact))}>{str(e.impact, "—")}</Badge>
                      <span className="text-[11px] text-[var(--fg-subtle)]">
                        {mins < 0 ? "just released" : `in ${formatCountdown(mins)}`}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <Label>Headlines</Label>
            {headlines.length > 0 ? (
              <AskButton onAsk={onAsk} prompt="Summarize the latest market headlines and explain what they mean for gold (XAUUSD) today.">
                What do they mean for gold?
              </AskButton>
            ) : null}
          </div>
          {headlines.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--fg-muted)]">
              {newsQ.isError ? "The news feed is unavailable right now." : "No headlines from the connected news feed."}
            </p>
          ) : (
            <ul className="mt-2 divide-y divide-[var(--border)]">
              {headlines.slice(0, 12).map((h, i) => {
                const url = str(h.url, "");
                return (
                  <li key={`${str(h.title)}-${i}`} className="py-2.5">
                    {url ? (
                      <a href={url} target="_blank" rel="noopener noreferrer" className="group inline-flex items-start gap-1 text-sm font-medium leading-snug hover:text-[var(--accent)]">
                        {str(h.title)}
                        <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 opacity-50 group-hover:opacity-100" />
                      </a>
                    ) : (
                      <p className="text-sm font-medium leading-snug">{str(h.title)}</p>
                    )}
                    <p className="mt-0.5 text-xs text-[var(--fg-muted)]">
                      {str(h.source, "Source not supplied")} · {relativeTime(str(h.published_at), now)}
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}


