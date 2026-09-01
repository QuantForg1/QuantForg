"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DialogTitle } from "@/components/ui/dialog";
import { str } from "@/lib/desk";
import {
  EXPLANATION_UNAVAILABLE,
  instrumentName,
  isHighConfidence,
  marketDataState,
  marketDirectionLabel,
  marketSignalLabel,
  presentField,
  presentLevel,
  presentPrice,
  presentUnavailable,
  rowRegime,
  rowSession,
  signalFreshness,
  signalFreshnessLabel,
  signalHumanExplanation,
  signalRiskRewardDisplay,
  signalScoreDisplay,
  signalStrengthBand,
  signalUpdatedAgo,
  SIGNALS_NOT_AUTHORIZATION,
  RESEARCH_SIGNAL,
} from "@/lib/trading/trader-ux";

export function directionTone(
  dir: string,
): "success" | "warning" | "danger" | "neutral" {
  if (dir === "BUY") return "success";
  if (dir === "SELL") return "danger";
  if (dir === "NEUTRAL") return "warning";
  return "neutral";
}

export function freshnessTone(
  state: string,
): "success" | "warning" | "danger" | "neutral" {
  if (state === "LIVE") return "success";
  if (state === "RECENT" || state === "STALE" || state === "PARTIAL") return "warning";
  if (state === "UNAVAILABLE" || state === "ERROR") return "danger";
  return "neutral";
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">{label}</dt>
      <dd className="font-mono text-sm tabular text-[var(--fg)]">{value}</dd>
    </div>
  );
}

export function IntelligenceDetail({
  row,
  kind,
}: {
  row: Record<string, unknown>;
  kind: "signal" | "market";
}) {
  const dir = marketDirectionLabel(row);
  const signal = marketSignalLabel(row);
  const freshness = signalFreshness(row);
  const explanation = signalHumanExplanation(row);
  const symbol = str(row.broker_symbol || row.symbol, "Instrument");
  const strength =
    signal === "NO SIGNAL" ? "Not available" : signalStrengthBand(row);
  const setupLine =
    dir === "BUY"
      ? "Bullish research setup"
      : dir === "SELL"
        ? "Bearish research setup"
        : dir === "NEUTRAL"
          ? "No actionable direction"
          : "Research setup";

  return (
    <div className="space-y-5 pr-2">
      <div>
        <DialogTitle>{symbol}</DialogTitle>
        <p className="mt-1 text-sm text-[var(--fg-muted)]">{setupLine}</p>
        <p className="mt-2 text-xs leading-relaxed text-[var(--fg-subtle)]">
          {kind === "signal" ? `${RESEARCH_SIGNAL}. ` : ""}
          {SIGNALS_NOT_AUTHORIZATION}
        </p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Badge tone={directionTone(dir)} aria-label={`Signal direction ${dir}`}>
          {signal}
        </Badge>
        <Badge tone={freshnessTone(freshness)}>{signalFreshnessLabel(freshness)}</Badge>
        <Badge tone="neutral">{presentUnavailable(presentField(row.asset_class))}</Badge>
        {isHighConfidence(row) ? <Badge tone="accent">Qualified</Badge> : null}
      </div>
      <dl className="grid gap-3 sm:grid-cols-2">
        {kind === "market" ? (
          <Detail label="Name" value={instrumentName(row)} />
        ) : null}
        <Detail
          label="Signal score"
          value={
            signal === "NO SIGNAL" || signalScoreDisplay(row) === "N/A"
              ? "N/A"
              : `${signalScoreDisplay(row)}/100`
          }
        />
        <Detail
          label="Market price"
          value={
            presentPrice(row.current_price ?? row.price ?? row.bid) === "Price unavailable"
              ? "N/A"
              : presentUnavailable(
                  presentPrice(row.current_price ?? row.price ?? row.bid),
                )
          }
        />
        <Detail
          label="Suggested entry"
          value={presentUnavailable(presentLevel(row.entry ?? row.entry_candidate, "Entry"))}
        />
        <Detail
          label="Stop loss"
          value={presentUnavailable(
            presentLevel(
              row.stop_loss ?? row.SL_candidate ?? row.sl_candidate ?? row.stop,
              "SL",
            ),
          )}
        />
        <Detail
          label="Take profit"
          value={presentUnavailable(
            presentLevel(
              row.take_profit ?? row.TP_candidate ?? row.tp_candidate ?? row.target,
              "TP",
            ),
          )}
        />
        <Detail label="Risk / Reward" value={signalRiskRewardDisplay(row)} />
        <Detail label="Strength" value={strength} />
        <Detail
          label="Market regime"
          value={presentUnavailable(presentField(rowRegime(row)))}
        />
        <Detail label="Signal freshness" value={signalUpdatedAgo(row)} />
        {kind === "market" ? (
          <>
            <Detail
              label="Bid"
              value={
                presentPrice(row.bid) === "Price unavailable"
                  ? "N/A"
                  : presentUnavailable(presentPrice(row.bid))
              }
            />
            <Detail
              label="Ask"
              value={
                presentPrice(row.ask) === "Price unavailable"
                  ? "N/A"
                  : presentUnavailable(presentPrice(row.ask))
              }
            />
            <Detail label="Trading status" value={marketDataState(row)} />
            <Detail
              label="Session"
              value={presentUnavailable(presentField(rowSession(row)))}
            />
          </>
        ) : null}
      </dl>
      <p className="text-sm leading-relaxed text-[var(--fg)]">
        {signal === "NO SIGNAL"
          ? "No signal evidence is available for this instrument."
          : explanation || EXPLANATION_UNAVAILABLE}
      </p>
      <div className="border-t border-[var(--border)] pt-4">
        <p className="text-xs leading-relaxed text-[var(--fg-muted)]">
          This is research intelligence, not a guaranteed trade outcome. There is no execute
          action on this desk.
        </p>
      </div>
      {kind === "market" ? (
        <Button variant="secondary" size="sm" asChild>
          <Link href={`/symbols/${encodeURIComponent(symbol)}`}>Open market page</Link>
        </Button>
      ) : null}
    </div>
  );
}
