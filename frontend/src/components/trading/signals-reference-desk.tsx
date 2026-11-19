"use client";

import type { ReactNode } from "react";
import {
  BarChart3,
  Clock,
  Coins,
  Crosshair,
  FileText,
  Minus,
  Scale,
  Shield,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { num, str } from "@/lib/desk";
import {
  TRADING_SYMBOL,
  displayTradingSymbolCode,
} from "@/lib/trading/gold-only";
import {
  signalBoardDirection,
  signalHumanExplanation,
  signalTimestamp,
} from "@/lib/trading/trader-ux";
import { cn } from "@/lib/utils";

const CONFIDENCE_SEGMENTS = 8;

function clockLabel(raw: unknown): string {
  if (raw == null || raw === "") return "Not available";
  const ms = typeof raw === "number" ? raw : Date.parse(String(raw));
  if (!Number.isFinite(ms)) return "Not available";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(ms);
}

function levelLabel(value: unknown): string {
  const n = num(value);
  if (!Number.isFinite(n)) return "Not available";
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function quoteLabel(value: unknown): string {
  const shown = levelLabel(value);
  return shown === "Not available" ? shown : `$${shown}`;
}

function confidencePct(row: Record<string, unknown> | null): number | null {
  if (!row) return null;
  const n = num(
    row.ai_confidence ?? row.confidence_state ?? row.confidence ?? row.opportunity_score,
  );
  if (!Number.isFinite(n)) return null;
  if (n <= 1) return Math.round(n * 100);
  if (n <= 100) return Math.round(n);
  return null;
}

function riskRewardLabel(row: Record<string, unknown> | null): string {
  if (!row) return "Not available";
  const n = num(row.RR ?? row.rr ?? row.risk_reward);
  if (!Number.isFinite(n) || n <= 0) return "Not available";
  return `1 : ${n.toFixed(2)}`;
}

function FieldRow({
  icon,
  label,
  value,
  tone = "default",
}: {
  icon: ReactNode;
  label: string;
  value: string;
  tone?: "default" | "profit" | "loss";
}) {
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 border-b border-[var(--border)] py-3 last:border-b-0">
      <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-2)] text-[var(--fg-muted)]">
        {icon}
      </span>
      <p className="min-w-0 flex-1 text-sm text-[var(--fg-muted)]">{label}</p>
      <p
        className={cn(
          "shrink-0 font-mono text-sm font-semibold tabular",
          tone === "profit" && "text-[var(--success)]",
          tone === "loss" && "text-[var(--danger)]",
          tone === "default" && "text-[var(--fg)]",
        )}
      >
        {value}
      </p>
    </div>
  );
}

/**
 * Single Trade Signal card. Figures come from the live research row.
 * The direction mark states the issued signal and does not place an order.
 */
export function SignalsReferenceDesk({
  row,
  quote,
  loading,
  unavailable,
}: {
  row: Record<string, unknown> | null;
  quote: number | null;
  loading: boolean;
  unavailable: boolean;
}) {
  const symbol = str(row?.broker_symbol || row?.symbol, TRADING_SYMBOL);
  const code = displayTradingSymbolCode(symbol);
  const dir = row ? signalBoardDirection(row) : "WAIT";
  const issued = String(row?.status || row?.badge || "").toUpperCase();
  const action =
    dir === "BUY" || dir === "SELL"
      ? dir
      : issued.includes("NO_TRADE") || issued.includes("NO TRADE")
        ? "NO TRADE"
        : "WAIT";
  const conf = confidencePct(row);
  const filled =
    conf == null ? 0 : Math.max(0, Math.min(CONFIDENCE_SEGMENTS, Math.round((conf / 100) * CONFIDENCE_SEGMENTS)));
  const price = row
    ? row.mid ?? row.price ?? row.current_price ?? row.close ?? quote
    : quote;
  const entry = row ? row.entry ?? row.entry_candidate ?? null : null;
  const analysis = !row
    ? unavailable
      ? "The research feed is unavailable. This card stays on the desk and shows the signal when the server sends one."
      : loading
        ? "Loading the current XAUUSD signal."
        : "No research signal has been issued for XAUUSD yet. This card stays on the desk and fills in when the server sends one."
    : signalHumanExplanation(row);

  return (
    <article
      className="min-w-0 overflow-hidden rounded-[28px] border border-[color-mix(in_srgb,var(--accent)_45%,var(--border))] bg-[var(--surface)]"
      aria-busy={loading}
      aria-label="Trade Signal"
    >
      <div className="grid min-w-0 lg:grid-cols-[minmax(0,0.86fr)_minmax(0,1.14fr)]">
        <div className="flex min-w-0 flex-col items-center justify-center gap-5 border-b border-[var(--border)] px-5 py-10 text-center lg:border-b-0 lg:border-r lg:px-8">
          <span className="inline-flex h-20 w-20 items-center justify-center rounded-full bg-[var(--accent-soft)] text-[var(--accent)]">
            <Coins className="h-9 w-9" aria-hidden />
          </span>
          <p className="rounded-full border border-[var(--border)] bg-[var(--surface-2)] px-4 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--fg-muted)]">
            Trade Signal
          </p>
          <div>
            <h2 className="text-4xl font-semibold tracking-tight text-[var(--fg)]">
              {code}
            </h2>
            <p className="mt-1 text-sm text-[var(--fg-muted)]">Gold / US Dollar</p>
          </div>
          <p className="max-w-full font-mono text-4xl font-semibold tabular tracking-tight text-[var(--fg)] sm:text-5xl">
            {quoteLabel(price)}
          </p>
          <p
            role="status"
            aria-label={`Signal direction ${action}. This does not place an order.`}
            className={cn(
              "inline-flex min-h-14 min-w-[11rem] items-center justify-center gap-2 rounded-full px-10 text-lg font-bold tracking-wide",
              action === "BUY" && "bg-[var(--buy)] text-white",
              action === "SELL" && "bg-[var(--danger)] text-white",
              action !== "BUY" && action !== "SELL" && "bg-[var(--surface-2)] text-[var(--fg)]",
            )}
          >
            {action === "SELL" ? (
              <TrendingDown className="h-5 w-5" aria-hidden />
            ) : action === "BUY" ? (
              <TrendingUp className="h-5 w-5" aria-hidden />
            ) : (
              <Minus className="h-5 w-5" aria-hidden />
            )}
            {action}
          </p>
        </div>

        <div className="min-w-0 p-3 sm:p-4">
          <div className="min-w-0 rounded-[22px] border border-[var(--border)] bg-[var(--bg)] px-4 py-2 sm:px-5">
          <FieldRow
            icon={<Crosshair className="h-4 w-4" aria-hidden />}
            label="Entry (Market)"
            value={levelLabel(entry)}
          />
          <FieldRow
            icon={<Target className="h-4 w-4" aria-hidden />}
            label="Take Profit (TP)"
            value={levelLabel(row?.take_profit ?? row?.TP_candidate)}
            tone="profit"
          />
          <FieldRow
            icon={<Shield className="h-4 w-4" aria-hidden />}
            label="Stop Loss (SL)"
            value={levelLabel(row?.stop_loss ?? row?.SL_candidate)}
            tone="loss"
          />
          <FieldRow
            icon={<Scale className="h-4 w-4" aria-hidden />}
            label="Risk / Reward"
            value={riskRewardLabel(row)}
          />
          <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2 border-b border-[var(--border)] py-3">
            <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-2)] text-[var(--fg-muted)]">
              <BarChart3 className="h-4 w-4" aria-hidden />
            </span>
            <p className="min-w-0 flex-1 text-sm text-[var(--fg-muted)]">Signal Confidence</p>
            <div className="flex shrink-0 items-center gap-2">
              <div
                className="flex gap-1"
                aria-hidden
              >
                {Array.from({ length: CONFIDENCE_SEGMENTS }, (_, index) => (
                  <span
                    key={index}
                    className={cn(
                      "h-2.5 w-3 rounded-[2px]",
                      index < filled ? "bg-[var(--success)]" : "bg-[var(--surface-3)]",
                    )}
                  />
                ))}
              </div>
              <p className="w-10 text-right font-mono text-sm font-semibold tabular text-[var(--fg)]">
                {conf == null ? "N/A" : `${conf}%`}
              </p>
            </div>
          </div>

          <div className="py-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-[var(--fg)]">
              <FileText className="h-4 w-4 text-[var(--fg-muted)]" aria-hidden />
              Analysis
            </div>
            <p className="text-sm leading-relaxed text-[var(--fg-muted)]">{analysis}</p>
          </div>

          <div className="flex min-w-0 flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] pt-3">
            <p className="inline-flex min-w-0 items-center gap-2 text-xs text-[var(--fg-muted)]">
              <Clock className="h-3.5 w-3.5 shrink-0" aria-hidden />
              <span className="truncate">
                Signal Time: {row ? clockLabel(signalTimestamp(row)) : "Not available"}
              </span>
            </p>
            <p className="rounded-full bg-[var(--accent-soft)] px-3 py-1 text-xs font-semibold tracking-wide text-[var(--accent)]">
              {code}
            </p>
          </div>
        </div>
        </div>
      </div>
    </article>
  );
}
