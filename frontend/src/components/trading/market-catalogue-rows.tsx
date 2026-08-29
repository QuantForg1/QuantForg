"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { marketDataState, scoreDisplay } from "@/lib/trading/trader-ux";
import { asRecord, str } from "@/lib/desk";

function toneForState(
  state: string,
): "success" | "warning" | "danger" | "neutral" {
  if (state === "LIVE") return "success";
  if (state === "STALE" || state === "MARKET_CLOSED" || state === "INSUFFICIENT_HISTORY") {
    return "warning";
  }
  if (
    state === "ERROR" ||
    state === "NO_DATA" ||
    state === "DISABLED" ||
    state === "UNSUPPORTED" ||
    state === "CATALOGUE_UNAVAILABLE"
  ) {
    return "danger";
  }
  return "neutral";
}

function toneForDirection(
  dir: string,
): "success" | "warning" | "neutral" {
  if (dir === "BUY") return "success";
  if (dir === "SELL") return "warning";
  return "neutral";
}

export function MarketCatalogueRows({
  rows,
  limit,
}: {
  rows: Record<string, unknown>[];
  limit?: number;
}) {
  const shown = limit != null ? rows.slice(0, limit) : rows;
  return (
    <ul className="grid min-w-0 gap-2">
      {shown.map((row, i) => {
        const symbol = str(
          row.broker_symbol,
          str(row.symbol, str(row.canonical_symbol, String(i))),
        );
        const dir = str(row.direction, "UNKNOWN").toUpperCase();
        const state = marketDataState(row);
        return (
          <li
            key={symbol}
            className="grid min-w-0 grid-cols-2 gap-2 rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 sm:grid-cols-3 lg:grid-cols-9"
          >
            <span className="truncate font-medium">{symbol}</span>
            <span className="truncate text-xs text-[var(--fg-muted)]">
              {str(row.asset_class, "UNKNOWN")}
            </span>
            <Badge tone={toneForState(state)}>{state}</Badge>
            <Badge tone={toneForDirection(dir.includes("BUY") ? "BUY" : dir.includes("SELL") ? "SELL" : dir)}>
              {dir.includes("BUY") ? "BUY" : dir.includes("SELL") ? "SELL" : dir === "WAIT" ? "WAIT" : "UNKNOWN"}
            </Badge>
            <span className="truncate text-xs text-[var(--fg-muted)]">
              {str(row.session, "UNKNOWN")}
            </span>
            <span className="truncate text-xs text-[var(--fg-muted)]">
              {str(
                asRecord(row.evidence).REGIME,
                str(row.regime, str(row.market_regime, "UNKNOWN")),
              )}
            </span>
            <span className="truncate text-xs tabular text-[var(--fg-muted)]">
              Opp {scoreDisplay(row.opportunity_score)}
            </span>
            <span className="truncate text-xs tabular text-[var(--fg-muted)]">
              Edge {scoreDisplay(row.directional_edge ?? row.edge)}
            </span>
            <span className="truncate text-xs tabular text-[var(--fg-muted)]">
              {scoreDisplay(row.confidence_state ?? row.confidence)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export function ResearchAdvisoryNote() {
  return (
    <p className="text-xs text-[var(--fg-subtle)]">
      RESEARCH · NOT A TRADE AUTHORIZATION.{" "}
      <Link href="/research" className="text-[var(--accent)] underline-offset-2 hover:underline">
        Open research
      </Link>
    </p>
  );
}
