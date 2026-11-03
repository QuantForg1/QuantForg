"use client";

import { useState } from "react";
import {
  Brain,
  CheckCircle2,
  Coins,
  Crosshair,
  Shield,
  Sparkles,
  Target,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { WorkspaceChart } from "@/components/workspace/chart-panel";
import { DirectionBadge } from "@/components/trading/signal-card";
import { freshnessTone } from "@/components/trading/intelligence-detail";
import { num, str } from "@/lib/desk";
import { TRADING_SYMBOL, displayTradingSymbol } from "@/lib/trading/gold-only";
import {
  presentField,
  presentLevel,
  scoreDisplay,
  signalBoardDirection,
  signalFreshness,
  signalFreshnessLabel,
  signalHumanExplanation,
  signalRiskRewardDisplay,
  signalTimestampLabel,
  signalWhyFactors,
  signalExecutionStatusLabel,
} from "@/lib/trading/trader-ux";
import { cn } from "@/lib/utils";

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p className="mt-1 truncate font-mono text-sm font-semibold tabular text-[var(--fg)]">
        {value}
      </p>
    </div>
  );
}

function DetailRow({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 border-b border-[var(--border)] py-3 last:border-b-0">
      <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          {label}
        </p>
        <div className="mt-1 text-sm font-medium text-[var(--fg)]">{children}</div>
      </div>
    </div>
  );
}

function confidencePct(row: Record<string, unknown>): number | null {
  const raw =
    row.ai_confidence ?? row.confidence_state ?? row.confidence ?? row.opportunity_score;
  const n = num(raw);
  if (!Number.isFinite(n)) return null;
  if (n <= 1) return Math.round(n * 100);
  if (n <= 100) return Math.round(n);
  return null;
}

function entryRange(row: Record<string, unknown>): string {
  const low = presentLevel(row.entry_low ?? row.entry_min ?? row.entry, "Entry");
  const high = presentLevel(row.entry_high ?? row.entry_max ?? row.entry_candidate, "Entry");
  if (low !== "—" && high !== "—" && low !== high) return `${low} – ${high}`;
  const single = presentLevel(row.entry ?? row.entry_candidate, "Entry");
  return single;
}

function analysisTags(row: Record<string, unknown>): string[] {
  const tags: string[] = [];
  const dir = signalBoardDirection(row);
  if (dir === "BUY") tags.push("Bullish Momentum");
  if (dir === "SELL") tags.push("Bearish Momentum");
  const regime = presentField(row.regime ?? row.market_regime);
  if (regime !== "Not available") tags.push(regime);
  const factors = signalWhyFactors(row);
  for (const f of factors) {
    if (tags.length >= 4) break;
    if (f.label === "Direction") continue;
    const short = f.value.length > 28 ? f.label : f.value;
    if (!tags.includes(short)) tags.push(short);
  }
  return tags.slice(0, 4);
}

/**
 * Reference-matched Signals desk composition.
 * All values come from the live signal row / MT5 candles — never sample mock figures.
 */
export function SignalsReferenceDesk({
  row,
  connected,
}: {
  row: Record<string, unknown>;
  connected: boolean;
}) {
  const [timeframe, setTimeframe] = useState("M15");
  const [chartType, setChartType] = useState<"candles" | "line" | "area">("candles");
  const [showVolume, setShowVolume] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);

  const symbol = str(row.broker_symbol || row.symbol, TRADING_SYMBOL);
  const dir = signalBoardDirection(row);
  const freshness = signalFreshness(row);
  const conf = confidencePct(row);
  const factors = signalWhyFactors(row);
  const explanation = signalHumanExplanation(row);
  const tags = analysisTags(row);
  const status = signalExecutionStatusLabel(row);
  const strategy = presentField(row.strategy ?? row.strategy_id ?? row.setup);
  const mid = num(row.mid ?? row.price ?? row.current_price ?? row.close);
  const strong =
    conf != null && conf >= 70
      ? dir === "BUY"
        ? "STRONG BUY"
        : dir === "SELL"
          ? "STRONG SELL"
          : null
      : null;
  const bannerLabel =
    strong ??
    (dir === "BUY" ? "BUY" : dir === "SELL" ? "SELL" : "WAIT");
  const bannerTone =
    dir === "BUY"
      ? "border-[color-mix(in_srgb,var(--success)_45%,var(--border))] bg-[color-mix(in_srgb,var(--success-soft)_70%,var(--surface))] text-[var(--success)]"
      : dir === "SELL"
        ? "border-[color-mix(in_srgb,var(--danger)_45%,var(--border))] bg-[color-mix(in_srgb,var(--danger-soft)_70%,var(--surface))] text-[var(--danger)]"
        : "border-[var(--border)] bg-[var(--bg)]/40 text-[var(--fg-muted)]";

  return (
    <div className="space-y-4">
      <article className="overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] p-4 shadow-[var(--shadow-card)] backdrop-blur-[8px] sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--warning-soft)] text-[var(--warning)]">
              <Coins className="h-6 w-6" aria-hidden />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-2xl font-semibold tracking-tight">
                  {displayTradingSymbol(symbol)}
                </h2>
                <Badge tone={freshnessTone(freshness)}>
                  {freshness === "LIVE" ? "LIVE" : signalFreshnessLabel(freshness)}
                </Badge>
              </div>
              <p className="mt-1 text-sm text-[var(--fg-muted)]">
                Gold Spot / US Dollar
              </p>
              <div className="mt-3">
                <span
                  className={cn(
                    "inline-flex items-center rounded-full border px-4 py-1.5 text-sm font-bold tracking-wide shadow-[0_0_24px_rgba(0,201,167,0.18)]",
                    bannerTone,
                  )}
                >
                  {bannerLabel}
                </span>
              </div>
            </div>
          </div>
          <p className="rounded-full border border-[var(--border)] px-3 py-1 text-xs text-[var(--fg-muted)]">
            {displayTradingSymbol(TRADING_SYMBOL)} (Gold)
          </p>
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <Metric label="Entry Range" value={entryRange(row)} />
          <Metric
            label="Take Profit"
            value={presentLevel(row.take_profit ?? row.TP_candidate, "TP")}
          />
          <Metric
            label="Stop Loss"
            value={presentLevel(row.stop_loss ?? row.SL_candidate, "SL")}
          />
          <Metric label="Risk/Reward" value={signalRiskRewardDisplay(row)} />
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Confidence
            </p>
            <p className="mt-1 font-mono text-sm font-semibold tabular">
              {conf == null ? scoreDisplay(row.ai_confidence ?? row.confidence) : `${conf}%`}
            </p>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--bg)]/70">
              <div
                className="h-full rounded-full bg-[var(--accent)]"
                style={{ width: conf == null ? "0%" : `${conf}%` }}
                aria-hidden
              />
            </div>
          </div>
        </div>
      </article>

      <div className="grid gap-4 xl:grid-cols-[1.45fr_0.9fr]">
        <section className="min-h-[360px] overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg-elevated)] shadow-[var(--shadow-card)]">
          <WorkspaceChart
            symbol={symbol}
            connected={connected}
            timeframe={timeframe}
            onTimeframeChange={setTimeframe}
            chartType={chartType}
            onChartTypeChange={setChartType}
            showVolume={showVolume}
            onShowVolumeChange={setShowVolume}
            fullscreen={fullscreen}
            onFullscreenChange={setFullscreen}
            lastPrice={Number.isFinite(mid) ? mid : undefined}
          />
        </section>

        <section className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] px-4 py-2 shadow-[var(--shadow-card)] backdrop-blur-[8px]">
          <h3 className="border-b border-[var(--border)] py-3 text-sm font-semibold">
            Signal Details
          </h3>
          <DetailRow icon={<Coins className="h-4 w-4" />} label="Symbol">
            {displayTradingSymbol(symbol)}
          </DetailRow>
          <DetailRow icon={<Crosshair className="h-4 w-4" />} label="Direction">
            <DirectionBadge dir={dir} />
          </DetailRow>
          <DetailRow icon={<Target className="h-4 w-4" />} label="Entry Range">
            <span className="font-mono tabular">{entryRange(row)}</span>
          </DetailRow>
          <DetailRow icon={<Sparkles className="h-4 w-4" />} label="Take Profit">
            <span className="font-mono tabular">
              {presentLevel(row.take_profit ?? row.TP_candidate, "TP")}
            </span>
          </DetailRow>
          <DetailRow icon={<Shield className="h-4 w-4" />} label="Stop Loss">
            <span className="font-mono tabular">
              {presentLevel(row.stop_loss ?? row.SL_candidate, "SL")}
            </span>
          </DetailRow>
          <DetailRow icon={<Target className="h-4 w-4" />} label="Risk/Reward">
            <span className="font-mono tabular">{signalRiskRewardDisplay(row)}</span>
          </DetailRow>
          <DetailRow icon={<Sparkles className="h-4 w-4" />} label="Confidence">
            <div>
              <p className="font-mono tabular">
                {conf == null
                  ? scoreDisplay(row.ai_confidence ?? row.confidence)
                  : `${conf}%`}
              </p>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--bg)]/70">
                <div
                  className="h-full rounded-full bg-[var(--accent)]"
                  style={{ width: conf == null ? "0%" : `${conf}%` }}
                  aria-hidden
                />
              </div>
            </div>
          </DetailRow>
          <DetailRow icon={<Brain className="h-4 w-4" />} label="Time Issued">
            {signalTimestampLabel(row) || "—"}
          </DetailRow>
          <DetailRow icon={<Brain className="h-4 w-4" />} label="Strategy">
            {strategy}
          </DetailRow>
          <DetailRow icon={<CheckCircle2 className="h-4 w-4" />} label="Status">
            <Badge tone={freshness === "LIVE" || freshness === "RECENT" ? "success" : "neutral"}>
              {status}
            </Badge>
          </DetailRow>
        </section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] p-4 shadow-[var(--shadow-card)] backdrop-blur-[8px]">
          <div className="mb-3 flex items-center gap-2">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[#7c5cff]/20 text-[#b7a4ff]">
              <Brain className="h-4 w-4" aria-hidden />
            </span>
            <h3 className="text-sm font-semibold">AI Signal Analysis</h3>
          </div>
          <p className="text-sm leading-relaxed text-[var(--fg-muted)]">{explanation}</p>
          {tags.length > 0 ? (
            <ul className="mt-4 flex flex-wrap gap-2">
              {tags.map((tag) => (
                <li
                  key={tag}
                  className="rounded-full border border-[var(--border)] bg-[var(--bg)]/40 px-3 py-1 text-xs font-medium text-[var(--fg-muted)]"
                >
                  {tag}
                </li>
              ))}
            </ul>
          ) : null}
        </section>

        <section className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] p-4 shadow-[var(--shadow-card)] backdrop-blur-[8px]">
          <div className="mb-3 flex items-center gap-2">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
              <Sparkles className="h-4 w-4" aria-hidden />
            </span>
            <h3 className="text-sm font-semibold">Key Factors</h3>
          </div>
          {factors.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">
              Key factors appear when the research payload includes evidence for this signal.
            </p>
          ) : (
            <ul className="space-y-2.5">
              {factors.slice(0, 6).map((factor) => (
                <li key={`${factor.label}:${factor.value}`} className="flex gap-2.5 text-sm">
                  <CheckCircle2
                    className={cn("mt-0.5 h-4 w-4 shrink-0 text-[var(--success)]")}
                    aria-hidden
                  />
                  <span>
                    <span className="font-medium text-[var(--fg)]">{factor.label}</span>
                    <span className="mt-0.5 block text-[var(--fg-muted)]">{factor.value}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
