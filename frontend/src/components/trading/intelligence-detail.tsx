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
      <dd className="font-mono text-sm tabular text-[var(--fg)]">{value}</dd>
    </div>
  );
}

const WHY_SECTIONS: Array<{ title: string; labels: string[] }> = [
  {
    title: "Signal",
    labels: ["Direction"],
  },
  {
    title: "Market regime",
    labels: ["Market regime", "Market condition", "Market", "Session"],
  },
  {
    title: "Key evidence",
    labels: [
      "Momentum",
      "Trend / structure",
      "Structure",
      "Volatility",
      "Zone",
      "Timing",
      "Liquidity",
      "Data quality",
    ],
  },
  {
    title: "Research interpretation",
    labels: ["Why this signal exists", "Why the model prefers this direction"],
  },
  {
    title: "Risk context",
    labels: ["Risk context", "Blockers", "Invalidation"],
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
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--fg-subtle)]">
          Why this signal
        </p>
        <DialogTitle className="mt-1">{symbol}</DialogTitle>
        <p className="mt-1 text-sm text-[var(--fg-muted)]">
          {kind === "signal" ? `${RESEARCH_SIGNAL}. ` : ""}
          {SIGNALS_NOT_AUTHORIZATION}
        </p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Badge
          tone={dir === "BUY" || dir === "SELL" ? directionTone(dir) : "neutral"}
          aria-label={`Signal direction ${dir}`}
        >
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
        <Detail
          label="Current price"
          value={
            presentPrice(row.current_price ?? row.price ?? row.bid) === "Price unavailable"
              ? "Not available"
              : presentPrice(row.current_price ?? row.price ?? row.bid)
          }
        />
        <Detail
          label="Entry"
          value={presentLevel(row.entry ?? row.entry_candidate, "Entry")}
        />
        <Detail
          label="Stop loss"
          value={presentLevel(
            row.stop_loss ?? row.SL_candidate ?? row.sl_candidate ?? row.stop,
            "SL",
          )}
        />
        <Detail
          label="Take profit"
          value={presentLevel(
            row.take_profit ?? row.TP_candidate ?? row.tp_candidate ?? row.target,
            "TP",
          )}
        />
        <Detail label="Risk/Reward" value={researchMetricDisplay(row, row.RR ?? row.rr)} />
        <Detail
          label="Strength"
          value={signal === "NO SIGNAL" ? "Not available" : signalStrength(row)}
        />
        <Detail
          label="Score"
          value={
            signal === "NO SIGNAL"
              ? "Not available"
              : presentField(row.research_rank_score) === "Not available"
                ? "Not available"
                : String(row.research_rank_score)
          }
        />
        <Detail label="Opportunity" value={score} />
        <Detail label="Edge" value={edge} />
        <Detail label="Regime" value={presentField(rowRegime(row))} />
        <Detail label="Timestamp" value={signalTimestampLabel(row)} />
        {kind === "market" ? (
          <>
            <Detail label="Bid" value={presentPrice(row.bid)} />
            <Detail label="Ask" value={presentPrice(row.ask)} />
            <Detail label="Trading status" value={marketDataState(row)} />
            <Detail label="Session" value={presentField(rowSession(row))} />
          </>
        ) : null}
      </dl>
      {signal === "NO SIGNAL" ? (
        <p className="text-sm text-[var(--fg-muted)]">No signal evidence is available for this instrument.</p>
      ) : whySections.length > 0 ? (
        <section className="space-y-4">
          {whySections.map((section) => (
            <div key={section.title}>
              <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                {section.title}
              </h3>
              <ul className="space-y-2">
                {section.items.map((factor) => (
                  <li
                    key={factor.label}
                    className="rounded-[var(--radius-sm)] bg-[var(--surface-2)] px-3 py-2"
                  >
                    <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                      {factor.label}
                    </p>
                    <p className="text-sm leading-relaxed text-[var(--fg)]">{factor.value}</p>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      ) : (
        <p className="text-sm text-[var(--fg-muted)]">{EXPLANATION_UNAVAILABLE}</p>
      )}
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
