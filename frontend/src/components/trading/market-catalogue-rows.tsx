"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  EMPTY_MARKET_FILTERS,
  filterMarketRows,
  instrumentName,
  instrumentSymbol,
  marketDataState,
  numericDisplay,
  presentAssetClasses,
  priceDisplay,
  rowDirection,
  rowRegime,
  rowSession,
  scoreDisplay,
  uniqueRowValues,
  type MarketFilterState,
} from "@/lib/trading/trader-ux";
import { str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 50;

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

function toneForDirection(dir: string): "success" | "warning" | "neutral" {
  if (dir === "BUY") return "success";
  if (dir === "SELL") return "warning";
  return "neutral";
}

function Chip({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "h-8 shrink-0 rounded-md border px-2.5 text-[11px] font-medium",
        active
          ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
          : "border-[var(--border)] text-[var(--fg-muted)] hover:border-[var(--border-strong)] hover:text-[var(--fg)]",
      )}
      aria-pressed={active}
    >
      {children}
    </button>
  );
}

export function MarketCatalogueRows({
  rows,
  limit,
  showFilters = false,
  compact = false,
}: {
  rows: Record<string, unknown>[];
  limit?: number;
  showFilters?: boolean;
  compact?: boolean;
}) {
  const [filters, setFilters] = useState<MarketFilterState>(EMPTY_MARKET_FILTERS);
  const [page, setPage] = useState(1);

  const classes = useMemo(() => presentAssetClasses(rows), [rows]);
  const sessions = useMemo(
    () => uniqueRowValues(rows, rowSession),
    [rows],
  );
  const regimes = useMemo(() => uniqueRowValues(rows, rowRegime), [rows]);
  const statuses = useMemo(
    () => uniqueRowValues(rows, (row) => marketDataState(row)),
    [rows],
  );

  const filtered = useMemo(
    () => (showFilters ? filterMarketRows(rows, filters) : rows),
    [filters, rows, showFilters],
  );
  const capped = limit != null ? filtered.slice(0, limit) : filtered;
  const pageCount = Math.max(1, Math.ceil(capped.length / PAGE_SIZE));
  const pageSafe = Math.min(page, pageCount);
  const shown =
    limit != null ? capped : capped.slice((pageSafe - 1) * PAGE_SIZE, pageSafe * PAGE_SIZE);

  const setFilter = (patch: Partial<MarketFilterState>) => {
    setPage(1);
    setFilters((prev) => ({ ...prev, ...patch }));
  };

  return (
    <div className="min-w-0 space-y-3">
      {showFilters ? (
        <div className="space-y-2">
          <label className="block min-w-0">
            <span className="sr-only">Search markets</span>
            <Input
              value={filters.q}
              onChange={(e) => setFilter({ q: e.target.value })}
              placeholder="Search symbol or name"
              aria-label="Search symbol or name"
              className="h-9"
            />
          </label>
          {classes.length > 0 ? (
            <div className="flex min-w-0 flex-wrap gap-1.5" role="group" aria-label="Asset class">
              <Chip active={filters.assetClass === "ALL"} onClick={() => setFilter({ assetClass: "ALL" })}>
                All
              </Chip>
              {classes.map((cls) => (
                <Chip
                  key={cls}
                  active={filters.assetClass === cls}
                  onClick={() => setFilter({ assetClass: cls })}
                >
                  {cls.charAt(0) + cls.slice(1).toLowerCase()}
                </Chip>
              ))}
            </div>
          ) : null}
          <div className="grid min-w-0 gap-2 sm:grid-cols-3">
            {sessions.length > 0 ? (
              <select
                className="h-9 min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-sm"
                value={filters.session}
                onChange={(e) => setFilter({ session: e.target.value })}
                aria-label="Session"
              >
                <option value="ALL">All sessions</option>
                {sessions.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            ) : null}
            {regimes.length > 0 ? (
              <select
                className="h-9 min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-sm"
                value={filters.regime}
                onChange={(e) => setFilter({ regime: e.target.value })}
                aria-label="Regime"
              >
                <option value="ALL">All regimes</option>
                {regimes.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            ) : null}
            {statuses.length > 0 ? (
              <select
                className="h-9 min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-sm"
                value={filters.status}
                onChange={(e) => setFilter({ status: e.target.value })}
                aria-label="Status"
              >
                <option value="ALL">All status</option>
                {statuses.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            ) : null}
          </div>
        </div>
      ) : null}

      {shown.length === 0 ? (
        <p className="py-6 text-center text-sm text-[var(--fg-muted)]">
          No instruments match these filters.
        </p>
      ) : (
        <>
          <div className={cn("hidden min-w-0 overflow-x-auto", compact ? "lg:block" : "md:block")}>
            <table className="w-full min-w-[720px] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                  <th className="py-2 pr-3 font-medium">Symbol</th>
                  <th className="py-2 pr-3 font-medium">Name</th>
                  <th className="py-2 pr-3 font-medium">Asset Class</th>
                  <th className="py-2 pr-3 font-medium">Bid</th>
                  <th className="py-2 pr-3 font-medium">Ask</th>
                  <th className="py-2 pr-3 font-medium">Spread</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 font-medium">Session</th>
                  <th className="py-2 pr-3 font-medium">Regime</th>
                  <th className="py-2 pr-3 font-medium">Opportunity</th>
                  <th className="py-2 font-medium">Direction</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((row, i) => {
                  const symbol = instrumentSymbol(row) || String(i);
                  const dir = rowDirection(row);
                  const state = marketDataState(row);
                  return (
                    <tr
                      key={symbol}
                      className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--surface-2)]"
                    >
                      <td className="py-2 pr-3">
                        <Link
                          href={`/symbols/${encodeURIComponent(symbol)}`}
                          className="font-medium text-[var(--fg)] underline-offset-2 hover:underline"
                        >
                          {symbol}
                        </Link>
                      </td>
                      <td className="max-w-[10rem] truncate py-2 pr-3 text-[var(--fg-muted)]">
                        {instrumentName(row)}
                      </td>
                      <td className="py-2 pr-3 text-[var(--fg-muted)]">
                        {str(row.asset_class, "UNKNOWN")}
                      </td>
                      <td className="py-2 pr-3 tabular">{priceDisplay(row.bid)}</td>
                      <td className="py-2 pr-3 tabular">{priceDisplay(row.ask)}</td>
                      <td className="py-2 pr-3 tabular">{numericDisplay(row.spread)}</td>
                      <td className="py-2 pr-3">
                        <Badge tone={toneForState(state)}>{state}</Badge>
                      </td>
                      <td className="py-2 pr-3 text-[var(--fg-muted)]">{rowSession(row)}</td>
                      <td className="py-2 pr-3 text-[var(--fg-muted)]">{rowRegime(row)}</td>
                      <td className="py-2 pr-3 tabular">{scoreDisplay(row.opportunity_score)}</td>
                      <td className="py-2">
                        <Badge tone={toneForDirection(dir)}>{dir}</Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <ul className={cn("grid min-w-0 gap-2", compact ? "lg:hidden" : "md:hidden")}>
            {shown.map((row, i) => {
              const symbol = instrumentSymbol(row) || String(i);
              const dir = rowDirection(row);
              const state = marketDataState(row);
              return (
                <li key={symbol}>
                  <Link
                    href={`/symbols/${encodeURIComponent(symbol)}`}
                    className="block min-w-0 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{symbol}</p>
                        <p className="truncate text-xs text-[var(--fg-muted)]">
                          {str(row.asset_class, "UNKNOWN")}
                        </p>
                      </div>
                      <Badge tone={toneForState(state)}>{state}</Badge>
                    </div>
                    <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                      <div>
                        <dt className="text-[var(--fg-subtle)]">Bid</dt>
                        <dd className="tabular">{priceDisplay(row.bid)}</dd>
                      </div>
                      <div>
                        <dt className="text-[var(--fg-subtle)]">Ask</dt>
                        <dd className="tabular">{priceDisplay(row.ask)}</dd>
                      </div>
                      <div>
                        <dt className="text-[var(--fg-subtle)]">Spread</dt>
                        <dd className="tabular">{numericDisplay(row.spread)}</dd>
                      </div>
                      <div>
                        <dt className="text-[var(--fg-subtle)]">Opportunity</dt>
                        <dd className="tabular">{scoreDisplay(row.opportunity_score)}</dd>
                      </div>
                    </dl>
                    <div className="mt-2">
                      <Badge tone={toneForDirection(dir)}>{dir}</Badge>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {limit == null && pageCount > 1 ? (
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-[var(--fg-subtle)]">
            {capped.length} instruments
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={pageSafe <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={pageSafe >= pageCount}
              onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
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
