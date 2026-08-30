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
  marketSignalLabel,
  presentField,
  priceDisplay,
  rowRegime,
  rowSession,
  scoreDisplay,
  signalBoardDirection,
  signalFreshness,
  signalStrength,
  signalTimestampLabel,
  signalWhyFactors,
  SIGNALS_NOT_AUTHORIZATION,
} from "@/lib/trading/trader-ux";

export function directionTone(
  dir: string,
): "success" | "warning" | "danger" | "neutral" {
  if (dir === "BUY") return "success";
  if (dir === "SELL") return "danger";
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
      <dd className="text-sm text-[var(--fg)]">{value}</dd>
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
  const dir = signalBoardDirection(row);
  const freshness = signalFreshness(row);
  const why = signalWhyFactors(row);
  const symbol = str(row.broker_symbol || row.symbol, "Instrument");

  return (
    <div className="space-y-4">
      <DialogTitle>{symbol}</DialogTitle>
      <p className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
        {SIGNALS_NOT_AUTHORIZATION}
      </p>
      <div className="flex flex-wrap gap-1.5">
        <Badge tone={directionTone(dir)}>{dir}</Badge>
        <Badge tone={freshnessTone(freshness)}>{freshness}</Badge>
        <Badge tone="neutral">{presentField(row.asset_class)}</Badge>
        {isHighConfidence(row) ? <Badge tone="accent">Qualified</Badge> : null}
      </div>
      <dl className="grid gap-3 sm:grid-cols-2">
        {kind === "market" ? (
          <Detail label="Name" value={instrumentName(row)} />
        ) : null}
        <Detail label="Asset class" value={presentField(row.asset_class)} />
        <Detail label="Trading status" value={marketDataState(row)} />
        <Detail label="Signal" value={marketSignalLabel(row)} />
        <Detail label="Direction" value={dir} />
        <Detail label="Opportunity" value={scoreDisplay(row.opportunity_score)} />
        <Detail label="Edge" value={scoreDisplay(row.directional_edge ?? row.edge)} />
        <Detail label="Risk/Reward" value={scoreDisplay(row.RR ?? row.rr)} />
        <Detail label="Strength" value={signalStrength(row)} />
        <Detail label="Session" value={presentField(rowSession(row))} />
        <Detail label="Regime" value={presentField(rowRegime(row))} />
        <Detail label="Market condition" value={presentField(row.market_condition ?? row.data_state)} />
        <Detail label="Data freshness" value={freshness} />
        <Detail label="Timestamp" value={signalTimestampLabel(row)} />
        {kind === "market" ? (
          <>
            <Detail label="Bid" value={priceDisplay(row.bid)} />
            <Detail label="Ask" value={priceDisplay(row.ask)} />
          </>
        ) : (
          <>
            <Detail label="Current price" value={priceDisplay(row.current_price ?? row.price ?? row.bid)} />
            <Detail label="Entry context" value={presentField(row.entry_candidate)} />
            <Detail label="Stop-loss context" value={presentField(row.sl_candidate ?? row.SL_candidate)} />
            <Detail label="Take-profit context" value={presentField(row.tp_candidate ?? row.TP_candidate)} />
          </>
        )}
        <Detail label="Risk status" value={presentField(row.risk_status ?? row.RISK_CONDITIONS)} />
      </dl>
      {why.length > 0 ? (
        <section>
          <h3 className="mb-2 text-sm font-medium text-[var(--fg)]">Why this signal exists</h3>
          <ul className="space-y-2">
            {why.map((factor) => (
              <li key={factor.label} className="rounded-md border border-[var(--border)] px-3 py-2">
                <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                  {factor.label}
                </p>
                <p className="text-sm text-[var(--fg)]">{factor.value}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <p className="text-sm text-[var(--fg-muted)]">{EXPLANATION_UNAVAILABLE}</p>
      )}
      <p className="text-xs text-[var(--fg-subtle)]">
        Research intelligence only. There is no execute or place-order action on this desk.
      </p>
      {kind === "market" ? (
        <Button variant="secondary" size="sm" asChild>
          <Link href={`/symbols/${encodeURIComponent(symbol)}`}>Open market page</Link>
        </Button>
      ) : null}
    </div>
  );
}
