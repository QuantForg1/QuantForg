"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Lock,
  Sparkles,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskError } from "@/components/desk/primitives";
import { useMarketDesk } from "@/components/trading/intelligence-desks";
import { billingApi, intelligenceApi } from "@/lib/api/endpoints";
import {
  biasTone,
  formatCountdown,
  formatPrice,
  formatUtcTime,
  impactTone,
  minutesUntil,
  relativeTime,
} from "@/lib/assistant/desk-format";
import { asList, asRecord, num, str } from "@/lib/desk";
import { tradingSessionLabel } from "@/lib/market/display-intelligence";
import { cn } from "@/lib/utils";

export type InsightTab = "overview" | "signal" | "analysis" | "news";

function Row({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] py-2.5 last:border-0">
      <span className="text-xs text-[var(--fg-muted)]">{label}</span>
      <span className="text-right">
        <span className="block text-sm font-semibold tabular-nums text-[var(--fg)]">{value}</span>
        {hint ? <span className="block text-[11px] text-[var(--fg-subtle)]">{hint}</span> : null}
      </span>
    </div>
  );
}

function Trend({ trend }: { trend: string }) {
  if (trend.startsWith("up")) return <ArrowUpRight className="h-4 w-4 text-[var(--success)]" aria-label="up" />;
  if (trend.startsWith("down")) return <ArrowDownRight className="h-4 w-4 text-[var(--danger)]" aria-label="down" />;
  return <ArrowRight className="h-4 w-4 text-[var(--fg-muted)]" aria-label="ranging" />;
}

function useNow(ms = 30_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(t);
  }, [ms]);
  return now;
}

function Loading() {
  return (
    <div className="space-y-2" aria-busy="true">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-9 animate-pulse rounded-md bg-[var(--surface-2)]" />
      ))}
    </div>
  );
}

/** Overview tab: one consistent read of the live gold market. */
function OverviewTab({ livePrice }: { livePrice?: number }) {
  const q = useMarketDesk();
  const now = useNow();
  if (q.isLoading) return <Loading />;
  if (!q.data) return <DeskError message="Live market data could not be loaded." onRetry={() => q.refetch()} />;
  const snap = asRecord(asRecord(q.data).snapshot);
  const quote = asRecord(snap.quote);
  const bias = asRecord(snap.bias);
  const vol = asRecord(snap.volatility_h1);
  const tfs = asList(snap.timeframes).map(asRecord);
  const h1 = tfs.find((t) => t.timeframe === "H1") ?? {};
  const bid = num(quote.bid);
  const price = Number.isFinite(livePrice ?? Number.NaN) ? (livePrice as number) : bid;
  const levels = asRecord(snap.key_levels_h1);
  const sup = num(asList(levels.supports)[0]);
  const res = num(asList(levels.resistances)[0]);
  const atr = num(h1.atr14);
  const direction = str(bias.direction, "unknown");
  const dist = (lv: number) =>
    Number.isFinite(lv) && Number.isFinite(price)
      ? `${Math.abs(lv - price).toFixed(2)} away${Number.isFinite(atr) && atr > 0 ? ` · ${(Math.abs(lv - price) / atr).toFixed(1)}× ATR` : ""}`
      : undefined;

  return (
    <div>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">Gold market</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{formatPrice(price)}</p>
          <p className="mt-0.5 flex items-center gap-1 text-[11px] text-[var(--fg-subtle)]">
            <Clock className="h-3 w-3" /> Analysis {formatUtcTime(str(snap.generated_at_utc, ""))}
          </p>
        </div>
        <Badge tone={biasTone(direction)}>
          {direction === "unknown"
            ? "Bias n/a"
            : `${direction[0].toUpperCase()}${direction.slice(1)} · ${num(bias.aligned)}/${num(bias.of)} TF`}
        </Badge>
      </div>

      <div className="mb-2 grid grid-cols-3 gap-2">
        {tfs.map((t) => (
          <div key={str(t.timeframe)} className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--fg-subtle)]">{str(t.timeframe)}</span>
              {t.available ? <Trend trend={str(t.trend, "")} /> : null}
            </div>
            <p className="mt-1 text-xs tabular-nums text-[var(--fg-muted)]">
              RSI {Number.isFinite(num(t.rsi14)) ? num(t.rsi14).toFixed(0) : "—"}
            </p>
          </div>
        ))}
      </div>

      <Row label="Resistance" value={Number.isFinite(res) ? formatPrice(res) : "—"} hint={dist(res)} />
      <Row label="Support" value={Number.isFinite(sup) ? formatPrice(sup) : "—"} hint={dist(sup)} />
      <Row
        label="Volatility"
        value={<span className="capitalize">{str(vol.state, "—")}</span>}
        hint={vol.atr_vs_average != null ? `${num(vol.atr_vs_average)}× average range` : undefined}
      />
      <Row label="Session" value={tradingSessionLabel(new Date(now))} hint="UTC" />
      <Row label="Spread" value={formatPrice(num(quote.spread))} />
    </div>
  );
}

/** Signal tab: paid feature — lock card for unpaid users. */
function SignalTab({
  topSignal,
  renderSignal,
}: {
  topSignal: Record<string, unknown> | null;
  renderSignal: (row: Record<string, unknown>) => ReactNode;
}) {
  const meQ = useQuery({ queryKey: ["billing-me"], queryFn: () => billingApi.me(), retry: 1, staleTime: 15_000 });
  const allowed = asRecord(asRecord(meQ.data).robot_access).allowed === true;
  if (meQ.isLoading) return <Loading />;
  if (!allowed && meQ.data) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-8 text-center">
        <span className="grid h-11 w-11 place-items-center rounded-full bg-[color-mix(in_srgb,var(--accent)_16%,transparent)]">
          <Lock className="h-5 w-5 text-[var(--accent)]" />
        </span>
        <p className="text-sm font-semibold">Signals are part of a QuantForg plan</p>
        <p className="max-w-xs text-xs text-[var(--fg-muted)]">
          Subscribe to see live gold signals with entry, stop loss and take profit.
        </p>
        <Link
          href="/pricing"
          className="rounded-full bg-[linear-gradient(180deg,#ff8a1f,#f25c05)] px-5 py-2 text-xs font-semibold text-white"
        >
          Subscribe
        </Link>
      </div>
    );
  }
  if (!topSignal) {
    return (
      <p className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 text-xs leading-relaxed text-[var(--fg-muted)]">
        No gold setup meets the robot&apos;s quality bar right now. It waits rather than forcing a trade.
      </p>
    );
  }
  return <div className="space-y-3">{renderSignal(topSignal)}</div>;
}

/** Analysis tab: measured trading conditions (not a signal). */
function AnalysisTab() {
  const q = useMarketDesk();
  if (q.isLoading) return <Loading />;
  if (!q.data) return <DeskError message="Trade conditions could not be loaded." onRetry={() => q.refetch()} />;
  const cond = asRecord(asRecord(q.data).conditions);
  const items = asList(cond.items).map(asRecord);
  const tone = str(cond.tone, "caution");
  const color = tone === "good" ? "var(--success)" : tone === "avoid" ? "var(--danger)" : "var(--warning)";
  const icon = (s: string) =>
    s === "good" ? (
      <CheckCircle2 className="h-4 w-4 text-[var(--success)]" />
    ) : s === "avoid" ? (
      <XCircle className="h-4 w-4 text-[var(--danger)]" />
    ) : (
      <AlertTriangle className="h-4 w-4 text-[var(--warning)]" />
    );
  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">Conditions now</p>
          <p className="text-sm font-semibold" style={{ color }}>
            {str(cond.verdict, "—")}
          </p>
        </div>
        <span className="text-2xl font-semibold tabular-nums" style={{ color }}>
          {Number.isFinite(num(cond.score)) ? num(cond.score) : "—"}
        </span>
      </div>
      <ul>
        {items.map((it) => (
          <li key={str(it.key)} className="flex items-start gap-2.5 border-b border-[var(--border)] py-2 last:border-0">
            <span className="mt-0.5">{icon(str(it.status))}</span>
            <span className="min-w-0">
              <span className="block text-xs font-medium">{str(it.label)}</span>
              <span className="block text-[11px] text-[var(--fg-muted)]">{str(it.detail)}</span>
            </span>
          </li>
        ))}
      </ul>
      <Link
        href="/intelligence"
        className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-[var(--accent)] hover:underline"
      >
        <Sparkles className="h-3.5 w-3.5" /> Ask QuantForg AI for a full analysis
      </Link>
    </div>
  );
}

/** News tab: next high-impact event, calendar and headlines. */
function NewsTab() {
  const now = useNow();
  const newsQ = useQuery({ queryKey: ["intelligence-news"], queryFn: () => intelligenceApi.news(20), retry: 2, staleTime: 60_000, refetchInterval: 120_000 });
  const calQ = useQuery({ queryKey: ["intelligence-calendar"], queryFn: () => intelligenceApi.calendar(30), retry: 2, staleTime: 60_000, refetchInterval: 120_000 });
  if (newsQ.isLoading || calQ.isLoading) return <Loading />;
  const events = asList(calQ.data)
    .map(asRecord)
    .filter((e) => str(e.title, "") && minutesUntil(str(e.scheduled_at), now) >= -30)
    .sort((a, b) => Date.parse(str(a.scheduled_at)) - Date.parse(str(b.scheduled_at)));
  const headlines = asList(newsQ.data).map(asRecord).filter((h) => str(h.title, ""));
  if (!events.length && !headlines.length) {
    if (newsQ.isError && calQ.isError) {
      return <DeskError message="News could not be loaded." onRetry={() => { void newsQ.refetch(); void calQ.refetch(); }} />;
    }
    return <p className="text-xs text-[var(--fg-muted)]">No upcoming events or headlines right now.</p>;
  }
  const next = events.find((e) => impactTone(str(e.impact)) === "danger" && minutesUntil(str(e.scheduled_at), now) >= 0);
  return (
    <div className="space-y-3">
      {next ? (
        <div className="rounded-xl border border-[color-mix(in_srgb,var(--danger)_40%,var(--border))] bg-[var(--surface-2)] px-3 py-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--danger)]">Next high-impact</p>
          <p className="text-sm font-semibold">{str(next.title)}</p>
          <p className="text-[11px] text-[var(--fg-muted)]">
            {str(next.country)} · in {formatCountdown(minutesUntil(str(next.scheduled_at), now))}
          </p>
        </div>
      ) : null}
      {events.length ? (
        <ul>
          {events.slice(0, 6).map((e, i) => (
            <li key={`${str(e.title)}-${i}`} className="flex items-center justify-between gap-2 border-b border-[var(--border)] py-2 last:border-0">
              <span className="min-w-0">
                <span className="block truncate text-xs font-medium">{str(e.title)}</span>
                <span className="block text-[11px] text-[var(--fg-subtle)]">
                  {str(e.country)} ·{" "}
                  {minutesUntil(str(e.scheduled_at), now) < 0 ? "just released" : `in ${formatCountdown(minutesUntil(str(e.scheduled_at), now))}`}
                </span>
              </span>
              <Badge tone={impactTone(str(e.impact))}>{str(e.impact, "—")}</Badge>
            </li>
          ))}
        </ul>
      ) : null}
      {headlines.length ? (
        <ul>
          {headlines.slice(0, 6).map((h, i) => (
            <li key={`${str(h.title)}-${i}`} className="border-b border-[var(--border)] py-2 last:border-0">
              {str(h.url, "") ? (
                <a href={str(h.url)} target="_blank" rel="noopener noreferrer" className="text-xs font-medium hover:text-[var(--accent)]">
                  {str(h.title)}
                </a>
              ) : (
                <span className="text-xs font-medium">{str(h.title)}</span>
              )}
              <span className="block text-[11px] text-[var(--fg-subtle)]">
                {str(h.source, "")} · {relativeTime(str(h.published_at), now)}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function OverviewInsightPanel({
  livePrice,
  topSignal,
  renderSignal,
}: {
  livePrice?: number;
  topSignal: Record<string, unknown> | null;
  renderSignal: (row: Record<string, unknown>) => ReactNode;
}) {
  const [tab, setTab] = useState<InsightTab>("overview");
  const tabs: Array<[InsightTab, string]> = [
    ["overview", "Overview"],
    ["signal", "Signal"],
    ["analysis", "Analysis"],
    ["news", "News"],
  ];
  return (
    <section className="qf-overview-panel flex min-h-[22rem] min-w-0 flex-col overflow-hidden lg:h-[34rem]">
      <div
        className="grid shrink-0 grid-cols-4 gap-1 border-b border-[color-mix(in_srgb,var(--accent)_16%,var(--border))] p-2"
        role="tablist"
        aria-label="Market insights"
      >
        {tabs.map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={cn(
              "h-8 rounded-lg text-xs font-semibold transition-colors",
              tab === id
                ? "bg-[var(--accent)] text-[var(--accent-fg)]"
                : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]",
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {tab === "overview" ? <OverviewTab livePrice={livePrice} /> : null}
        {tab === "signal" ? <SignalTab topSignal={topSignal} renderSignal={renderSignal} /> : null}
        {tab === "analysis" ? <AnalysisTab /> : null}
        {tab === "news" ? <NewsTab /> : null}
      </div>
    </section>
  );
}
