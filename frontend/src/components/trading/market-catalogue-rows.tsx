"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { FilterChip } from "@/components/trading/filter-chip";
import { IntelligenceDetail, directionTone, freshnessTone } from "@/components/trading/intelligence-detail";
import {
  EMPTY_MARKET_FILTERS,
  MARKET_PAGE_SIZE,
  cataloguePageSlice,
  filterMarketRows,
  hasResearchSignal,
  instrumentSymbol,
  marketDirectionLabel,
  marketSignalLabel,
  presentAssetClasses,
  presentField,
  researchMetricDisplay,
  rowRegime,
  rowSession,
  signalFreshness,
  sortSignalRows,
  uniqueRowValues,
  type MarketFilterState,
  type SignalSortKey,
} from "@/lib/trading/trader-ux";
import { str } from "@/lib/desk";
import { cn } from "@/lib/utils";

export function MarketCatalogueRows({
  rows,
  limit,
  showFilters = false,
  compact = false,
  enableDetail = true,
}: {
  rows: Record<string, unknown>[];
  limit?: number;
  showFilters?: boolean;
  compact?: boolean;
  enableDetail?: boolean;
}) {
  const [filters, setFilters] = useState<MarketFilterState>(EMPTY_MARKET_FILTERS);
  const [searchInput, setSearchInput] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<SignalSortKey>("instrument");
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setFilters((prev) => (prev.q === searchInput ? prev : { ...prev, q: searchInput }));
    }, 200);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const classes = useMemo(() => presentAssetClasses(rows), [rows]);
  const sessions = useMemo(() => uniqueRowValues(rows, rowSession), [rows]);
  const regimes = useMemo(() => uniqueRowValues(rows, rowRegime), [rows]);
  const statuses = useMemo(
    () => uniqueRowValues(rows, (row) => signalFreshness(row)),
    [rows],
  );
  const directions = useMemo(
    () =>
      uniqueRowValues(rows, (row) =>
        hasResearchSignal(row) ? marketDirectionLabel(row) : "",
      ).filter((d) => d === "BUY" || d === "SELL"),
    [rows],
  );

  const filtered = useMemo(
    () => (showFilters ? filterMarketRows(rows, filters) : rows),
    [filters, rows, showFilters],
  );
  const ordered = useMemo(() => sortSignalRows(filtered, sort), [filtered, sort]);
  const capped = limit != null ? ordered.slice(0, limit) : ordered;
  const pageCount = Math.max(1, Math.ceil(capped.length / MARKET_PAGE_SIZE));
  const pageSafe = Math.min(page, pageCount);
  const shown =
    limit != null ? capped : cataloguePageSlice(capped, pageSafe, MARKET_PAGE_SIZE);
  const rangeStart = capped.length === 0 ? 0 : (pageSafe - 1) * MARKET_PAGE_SIZE + 1;
  const rangeEnd = Math.min(pageSafe * MARKET_PAGE_SIZE, capped.length);

  const setFilter = (patch: Partial<MarketFilterState>) => {
    setPage(1);
    setFilters((prev) => ({ ...prev, ...patch }));
  };

  const openRow = (row: Record<string, unknown>) => {
    if (enableDetail) setSelected(row);
  };

  return (
    <div className="min-w-0 space-y-3">
      {showFilters ? (
        <div className="space-y-2">
          <label className="block min-w-0">
            <span className="sr-only">Search markets</span>
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search symbol or name"
              aria-label="Search symbol or name"
              className="h-9"
            />
          </label>
          {classes.length > 0 ? (
            <div className="flex min-w-0 flex-wrap gap-1.5" role="group" aria-label="Asset class">
              <FilterChip active={filters.assetClass === "ALL"} onClick={() => setFilter({ assetClass: "ALL" })}>
                All
              </FilterChip>
              {classes.map((cls) => (
                <FilterChip
                  key={cls}
                  active={filters.assetClass === cls}
                  onClick={() => setFilter({ assetClass: cls })}
                >
                  {cls.charAt(0) + cls.slice(1).toLowerCase()}
                </FilterChip>
              ))}
            </div>
          ) : null}
          {directions.length > 0 ? (
            <div className="flex min-w-0 flex-wrap gap-1.5" role="group" aria-label="Direction">
              <FilterChip
                active={filters.direction === "ALL"}
                onClick={() => setFilter({ direction: "ALL" })}
              >
                All
              </FilterChip>
              {directions.map((dir) => (
                <FilterChip
                  key={dir}
                  active={filters.direction === dir}
                  onClick={() => setFilter({ direction: dir })}
                >
                  {dir}
                </FilterChip>
              ))}
            </div>
          ) : null}
          <div className="grid min-w-0 gap-2 sm:grid-cols-4">
            {sessions.length > 0 ? (
              <select
                className="h-9 min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
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
                className="h-9 min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
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
                className="h-9 min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                value={filters.freshness}
                onChange={(e) => setFilter({ freshness: e.target.value })}
                aria-label="Freshness"
              >
                <option value="ALL">All freshness</option>
                {statuses.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label htmlFor="market-sort" className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
              Sort
            </label>
            <select
              id="market-sort"
              className="h-9 min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
              value={sort}
              onChange={(e) => {
                setPage(1);
                setSort(e.target.value as SignalSortKey);
              }}
              aria-label="Sort markets"
            >
              <option value="instrument">Symbol</option>
              <option value="asset_class">Asset class</option>
              <option value="signal">Signal</option>
              <option value="strongest">Signal rank</option>
              <option value="opportunity">Opportunity</option>
              <option value="edge">Edge</option>
              <option value="risk_reward">RR</option>
              <option value="freshness">Freshness</option>
            </select>
            <p className="text-xs text-[var(--fg-subtle)]">
              {capped.length} instrument{capped.length === 1 ? "" : "s"}
              {capped.length !== rows.length ? ` of ${rows.length}` : ""}
            </p>
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
            <table className="w-full min-w-[800px] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                  <th className="py-2 pr-3 font-medium" scope="col">Symbol</th>
                  <th className="py-2 pr-3 font-medium" scope="col">Asset Class</th>
                  <th className="py-2 pr-3 font-medium" scope="col">Session</th>
                  <th className="py-2 pr-3 font-medium" scope="col">Regime</th>
                  <th className="py-2 pr-3 font-medium" scope="col">Signal</th>
                  <th className="py-2 pr-3 font-medium" scope="col">Direction</th>
                  <th className="py-2 pr-3 font-medium" scope="col">Opportunity</th>
                  <th className="py-2 pr-3 font-medium" scope="col">Edge</th>
                  <th className="py-2 pr-3 font-medium" scope="col">R/R</th>
                  <th className="py-2 font-medium" scope="col">Freshness</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((row, i) => {
                  const symbol = instrumentSymbol(row) || String(i);
                  const dir = marketDirectionLabel(row);
                  const freshness = signalFreshness(row);
                  return (
                    <tr
                      key={symbol}
                      className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--surface-2)]"
                    >
                      <td className="py-2 pr-3">
                        {enableDetail ? (
                          <button
                            type="button"
                            onClick={() => openRow(row)}
                            className="font-medium text-[var(--fg)] underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                          >
                            {symbol}
                          </button>
                        ) : (
                          <span className="font-medium text-[var(--fg)]">{symbol}</span>
                        )}
                      </td>
                      <td className="py-2 pr-3 text-[var(--fg-muted)]">
                        {str(row.asset_class, "UNKNOWN")}
                      </td>
                      <td className="py-2 pr-3 text-[var(--fg-muted)]">{rowSession(row)}</td>
                      <td className="py-2 pr-3 text-[var(--fg-muted)]">{rowRegime(row)}</td>
                      <td className="py-2 pr-3">{marketSignalLabel(row)}</td>
                      <td className="py-2 pr-3">
                        {dir === "—" ? (
                          <span className="text-[var(--fg-muted)]">—</span>
                        ) : (
                          <Badge tone={directionTone(dir)}>{dir}</Badge>
                        )}
                      </td>
                      <td className="py-2 pr-3 tabular">
                        {researchMetricDisplay(row, row.opportunity_score)}
                      </td>
                      <td className="py-2 pr-3 tabular">
                        {researchMetricDisplay(row, row.directional_edge ?? row.edge)}
                      </td>
                      <td className="py-2 pr-3 tabular">
                        {researchMetricDisplay(row, row.RR ?? row.rr)}
                      </td>
                      <td className="py-2">
                        <Badge tone={freshnessTone(freshness)}>{freshness}</Badge>
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
              const dir = marketDirectionLabel(row);
              const signal = marketSignalLabel(row);
              const freshness = signalFreshness(row);
              return (
                <li key={symbol}>
                  {enableDetail ? (
                  <button
                    type="button"
                    onClick={() => openRow(row)}
                    className="block w-full min-w-0 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{symbol}</p>
                        <p className="truncate text-xs text-[var(--fg-muted)]">
                          {str(row.asset_class, "UNKNOWN")} · {presentField(rowSession(row))}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        <Badge tone={dir === "BUY" || dir === "SELL" ? directionTone(dir) : "neutral"}>
                          {signal}
                        </Badge>
                        <Badge tone={freshnessTone(freshness)}>{freshness}</Badge>
                      </div>
                    </div>
                    <dl className="mt-2 grid grid-cols-3 gap-x-3 gap-y-1 text-xs">
                      <div>
                        <dt className="text-[var(--fg-subtle)]">Opportunity</dt>
                        <dd className="tabular">{researchMetricDisplay(row, row.opportunity_score)}</dd>
                      </div>
                      <div>
                        <dt className="text-[var(--fg-subtle)]">Edge</dt>
                        <dd className="tabular">
                          {researchMetricDisplay(row, row.directional_edge ?? row.edge)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-[var(--fg-subtle)]">R/R</dt>
                        <dd className="tabular">{researchMetricDisplay(row, row.RR ?? row.rr)}</dd>
                      </div>
                    </dl>
                  </button>
                  ) : (
                    <div className="min-w-0 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate font-medium">{symbol}</p>
                          <p className="truncate text-xs text-[var(--fg-muted)]">
                            {str(row.asset_class, "UNKNOWN")} · {presentField(rowSession(row))}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          <Badge tone={dir === "BUY" || dir === "SELL" ? directionTone(dir) : "neutral"}>
                            {signal}
                          </Badge>
                          <Badge tone={freshnessTone(freshness)}>{freshness}</Badge>
                        </div>
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}

      {limit == null ? (
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-[var(--fg-subtle)]">
            {capped.length === 0
              ? "0 instruments"
              : `Showing ${rangeStart}–${rangeEnd} of ${capped.length}`}
            {pageCount > 1 ? ` · page ${pageSafe} of ${pageCount}` : ""}
          </p>
          {pageCount > 1 ? (
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
          ) : null}
        </div>
      ) : null}

      {enableDetail ? (
        <Dialog open={selected != null} onOpenChange={(open) => !open && setSelected(null)}>
          <DialogContent className="w-[min(96vw,720px)]">
            {selected ? <IntelligenceDetail row={selected} kind="market" /> : null}
          </DialogContent>
        </Dialog>
      ) : null}
    </div>
  );
}

export function ResearchAdvisoryNote() {
  return (
    <p className="text-xs text-[var(--fg-subtle)]">
      RESEARCH · NOT A TRADE AUTHORIZATION.
    </p>
  );
}
