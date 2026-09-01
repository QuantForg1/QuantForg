"use client";

import { Badge } from "@/components/ui/badge";
import { str } from "@/lib/desk";
import { cn } from "@/lib/utils";
import {
  presentField,
  presentLevel,
  presentPrice,
  rowRegime,
  scoreDisplay,
  signalBoardDirection,
  signalCardTone,
  signalFreshness,
  signalFreshnessLabel,
  signalMt5Ticket,
  signalStrength,
  signalTimestampLabel,
  signalHumanExplanation,
  signalExecutionStatusLabel,
  signalKindLabel,
  signalWaitingReason,
} from "@/lib/trading/trader-ux";
import { freshnessTone } from "@/components/trading/intelligence-detail";

export function DirectionBadge({
  dir,
  className,
}: {
  dir: string;
  className?: string;
}) {
  return (
    <Badge
      tone={
        dir === "BUY" ? "success" : dir === "SELL" ? "danger" : dir === "NEUTRAL" ? "warning" : "neutral"
      }
      className={cn("font-semibold tracking-[0.08em]", className)}
      aria-label={`Signal direction ${dir}`}
    >
      {dir}
    </Badge>
  );
}

function displayPrice(value: unknown): string {
  const shown = presentPrice(value);
  return shown === "Price unavailable" ? "Not available" : shown;
}

function displayScore(value: unknown): string {
  const shown = scoreDisplay(value);
  return shown === "UNKNOWN" || shown === "—" ? "Not available" : shown;
}

function displayTimestamp(row: Record<string, unknown>): string {
  const raw = signalTimestampLabel(row);
  if (!raw || raw === "—" || raw === "Not available") return "Not available";
  const ms = Date.parse(raw);
  if (!Number.isFinite(ms)) return raw;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(ms);
}

export function SignalCard({
  row,
  onOpen,
  compact = false,
}: {
  row: Record<string, unknown>;
  onOpen: () => void;
  compact?: boolean;
}) {
  const dir = signalBoardDirection(row);
  const symbol = str(row.broker_symbol || row.symbol, "—");
  const freshness = signalFreshness(row);
  const asset = presentField(row.asset_class);
  const statusLabel = signalExecutionStatusLabel(row);
  const statusTone = signalCardTone(row);
  const ticket = signalMt5Ticket(row);
  const waiting = signalWaitingReason(row);
  const timeframe = presentField(row.timeframe ?? row.entry_timeframe ?? row.tf);
  const strategy = presentField(row.strategy ?? row.strategy_id ?? row.setup);
  const executed = Boolean(ticket);

  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "relative h-full w-full overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-elevated)] text-left shadow-[var(--shadow-card)] transition duration-[var(--duration-os)] hover:border-[var(--border-strong)] hover:shadow-[var(--shadow-card-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
        compact ? "p-3" : "p-4",
      )}
    >
      <span
        className={cn(
          "absolute inset-y-0 left-0 w-[3px]",
          dir === "BUY" && "bg-[var(--buy)]",
          dir === "SELL" && "bg-[var(--sell)]",
          dir !== "BUY" && dir !== "SELL" && "bg-[var(--border-strong)]",
        )}
        aria-hidden
      />
      <div className="flex items-start justify-between gap-3 pl-1">
        <div className="min-w-0">
          <p className="truncate text-[1.05rem] font-semibold tracking-tight text-[var(--fg)]">
            {symbol}
          </p>
          <p className="mt-0.5 text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            {asset}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <DirectionBadge dir={dir} />
          <Badge tone={statusTone} aria-label={`Signal status ${statusLabel}`}>
            {statusLabel}
          </Badge>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 pl-1">
        <div>
          <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
            Strength
          </p>
          <p className="mt-0.5 font-mono text-xl font-semibold tabular leading-none text-[var(--fg)]">
            {signalStrength(row)}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
            Current price
          </p>
          <p className="mt-0.5 font-mono text-xl font-semibold tabular leading-none text-[var(--fg)]">
            {displayPrice(row.price ?? row.mid ?? row.bid)}
          </p>
        </div>
      </div>

      {compact ? (
        <p className="mt-3 pl-1 text-[11px] text-[var(--fg-muted)]">
          {waiting && !ticket ? `${statusLabel}: ${waiting}` : signalHumanExplanation(row)}
        </p>
      ) : (
        <>
          <dl className="mt-4 grid grid-cols-2 gap-x-3 gap-y-2 border-t border-[var(--border)] pt-3 pl-1 sm:grid-cols-4">
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Entry
              </dt>
              <dd className="font-mono text-sm tabular">
                {presentLevel(row.entry ?? row.entry_candidate, "Entry")}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Stop loss
              </dt>
              <dd className="font-mono text-sm tabular">
                {presentLevel(row.stop_loss ?? row.SL_candidate, "SL")}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Take profit
              </dt>
              <dd className="font-mono text-sm tabular">
                {presentLevel(row.take_profit ?? row.TP_candidate, "TP")}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Risk/Reward
              </dt>
              <dd className="font-mono text-sm tabular">
                {displayScore(row.RR ?? row.rr)}
              </dd>
            </div>
          </dl>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 pl-1 text-[11px] text-[var(--fg-muted)]">
            <span>{presentField(rowRegime(row))}</span>
            <span className="tabular">{timeframe}</span>
            <span className="tabular">{displayTimestamp(row)}</span>
            <Badge tone={freshnessTone(freshness)}>
              {signalFreshnessLabel(freshness)}
            </Badge>
          </div>
          <p className="mt-2 pl-1 text-[11px] text-[var(--fg-subtle)]">
            {signalKindLabel(row)}
            {strategy !== "Not available" ? ` · ${strategy}` : ""}
          </p>
          {executed ? (
            <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 border-t border-[var(--border)] pt-3 pl-1 text-[11px] sm:grid-cols-4">
              <div>
                <dt className="uppercase tracking-wide text-[var(--fg-subtle)]">MT5 ticket</dt>
                <dd className="font-mono tabular text-[var(--fg)]">{ticket}</dd>
              </div>
              <div>
                <dt className="uppercase tracking-wide text-[var(--fg-subtle)]">Fill</dt>
                <dd className="font-mono tabular">
                  {presentLevel(row.entry_price ?? row.fill_price ?? row.entry, "Entry")}
                </dd>
              </div>
              <div>
                <dt className="uppercase tracking-wide text-[var(--fg-subtle)]">Volume</dt>
                <dd className="font-mono tabular">{presentField(row.volume ?? row.lots)}</dd>
              </div>
              <div>
                <dt className="uppercase tracking-wide text-[var(--fg-subtle)]">Executed</dt>
                <dd className="tabular">{displayTimestamp(row)}</dd>
              </div>
            </dl>
          ) : null}
          {waiting && statusLabel !== "EXECUTED" ? (
            <p className="mt-3 line-clamp-2 pl-1 font-mono text-[11px] text-[var(--fg-muted)]">
              {statusLabel === "WAITING" ? `Waiting: ${waiting}` : waiting}
            </p>
          ) : null}
          <p className="mt-3 line-clamp-2 pl-1 text-[12px] leading-relaxed text-[var(--fg-muted)]">
            {signalHumanExplanation(row)}
          </p>
        </>
      )}
    </button>
  );
}
