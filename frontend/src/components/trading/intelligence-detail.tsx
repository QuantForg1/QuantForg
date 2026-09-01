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
  priceDisplay,
  researchMetricDisplay,
  rowRegime,
  rowSession,
  signalFreshness,
  signalFreshnessLabel,
  signalStrength,
  signalTimestampLabel,
  signalWhyFactors,
  SIGNALS_NOT_AUTHORIZATION,
  RESEARCH_SIGNAL,
  type SignalWhyFactor,
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

const WHY_SECTIONS: Array<{ title: string; labels: string[] }> = [
  {
    title: "Signal",
    labels: ["Direction", "Why this signal exists", "Why the model prefers this direction"],
  },
  {
    title: "Market condition",
    labels: ["Market condition", "Market", "Market regime", "Session"],
  },
  {
    title: "Price structure",
    labels: ["Structure", "Trend / structure", "Zone"],
  },
  { title: "Momentum", labels: ["Momentum"] },
  { title: "Trend", labels: ["Trend / structure"] },
  { title: "Volatility", labels: ["Volatility"] },
  {
    title: "Technical evidence",
    labels: ["Timing", "Liquidity", "Data quality"],
  },
  {
    title: "Risk context",
    labels: ["Risk context", "Blockers", "Invalidation"],
  },
  {
    title: "Model reasoning",
    labels: ["Why this signal exists", "Why the model prefers this direction"],
  },
];

function groupedWhy(factors: SignalWhyFactor[]): Array<{
  title: string;
  items: SignalWhyFactor[];
}> {
  const used = new Set<string>();
  const sections: Array<{ title: string; items: SignalWhyFactor[] }> = [];
  for (const section of WHY_SECTIONS) {
    const items = factors.filter(
      (factor) => section.labels.includes(factor.label) && !used.has(factor.label),
    );
    if (items.length === 0) continue;
    items.forEach((item) => used.add(item.label));
    sections.push({ title: section.title, items });
  }
  const leftover = factors.filter((factor) => !used.has(factor.label));
  if (leftover.length > 0) {
    sections.push({ title: "Additional evidence", items: leftover });
  }
  return sections;
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
  const why = signalWhyFactors(row);
  const whySections = groupedWhy(why);
  const symbol = str(row.broker_symbol || row.symbol, "Instrument");
  const score = researchMetricDisplay(row, row.opportunity_score);
  const edge = researchMetricDisplay(row, row.directional_edge ?? row.edge);

  return (
    <div className="space-y-5 pr-2">
      <div>
        <DialogTitle>{symbol}</DialogTitle>
        <p className="mt-1 text-[11px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {kind === "signal" ? `${RESEARCH_SIGNAL} · ` : ""}
          {SIGNALS_NOT_AUTHORIZATION}
        </p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Badge tone={dir === "BUY" || dir === "SELL" ? directionTone(dir) : "neutral"}>
          {signal}
        </Badge>
        <Badge tone={freshnessTone(freshness)}>{signalFreshnessLabel(freshness)}</Badge>
        <Badge tone="neutral">{presentField(row.asset_class)}</Badge>
        {isHighConfidence(row) ? <Badge tone="accent">Qualified</Badge> : null}
      </div>
      <dl className="grid gap-3 sm:grid-cols-2">
        {kind === "market" ? (
          <Detail label="Name" value={instrumentName(row)} />
        ) : null}
        <Detail label="Asset class" value={presentField(row.asset_class)} />
        <Detail label="Trading status" value={marketDataState(row)} />
        <Detail label="Signal" value={signal} />
        <Detail label="Direction" value={dir} />
        <Detail label="Opportunity" value={score} />
        <Detail label="Edge" value={edge} />
        <Detail label="Risk/Reward" value={researchMetricDisplay(row, row.RR ?? row.rr)} />
        <Detail
          label="Strength"
          value={signal === "NO SIGNAL" ? "—" : signalStrength(row)}
        />
        <Detail
          label="Confidence / score"
          value={
            signal === "NO SIGNAL"
              ? "—"
              : presentField(row.research_rank_score) === "Not available"
                ? "UNAVAILABLE"
                : String(row.research_rank_score)
          }
        />
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
            <Detail
              label="Signal type"
              value={presentField(row.signal_type ?? row.entry_type)}
            />
            <Detail
              label="Entry"
              value={presentField(row.entry ?? row.entry_candidate)}
            />
            <Detail
              label="Stop loss"
              value={presentField(
                row.stop_loss ?? row.SL_candidate ?? row.sl_candidate ?? row.stop,
              )}
            />
            <Detail
              label="Take profit"
              value={presentField(
                row.take_profit ?? row.TP_candidate ?? row.tp_candidate ?? row.target,
              )}
            />
          </>
        )}
        <Detail label="Risk status" value={presentField(row.risk_status ?? row.RISK_CONDITIONS)} />
      </dl>
      {signal === "NO SIGNAL" ? (
        <p className="text-sm text-[var(--fg-muted)]">NO SIGNAL</p>
      ) : whySections.length > 0 ? (
        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-[var(--fg)]">Why this signal</h3>
          {whySections.map((section) => (
            <div key={section.title}>
              <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                {section.title}
              </h4>
              <ul className="space-y-2">
                {section.items.map((factor) => (
                  <li
                    key={factor.label}
                    className="rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2"
                  >
                    <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                      {factor.label}
                    </p>
                    <p className="text-sm text-[var(--fg)]">{factor.value}</p>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <p className="text-sm text-[var(--fg)]">
            Research conclusion: {dir} — {RESEARCH_SIGNAL}
          </p>
        </section>
      ) : (
        <p className="text-sm text-[var(--fg-muted)]">{EXPLANATION_UNAVAILABLE}</p>
      )}
      <div className="border-t border-[var(--border)] pt-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--fg-subtle)]">
          Research intelligence
        </p>
        <p className="mt-1 text-xs text-[var(--fg-muted)]">
          Not trade authorization. There is no execute or place-order action on this desk.
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
