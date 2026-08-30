"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity, Radar } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { DeskEmpty, DeskMetric, DeskSkeleton } from "@/components/desk/primitives";
import { FilterChip } from "@/components/trading/filter-chip";
import { IntelligenceDetail, directionTone, freshnessTone } from "@/components/trading/intelligence-detail";
import { marketUniverseApi, tradingSessionApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import {
  catalogueViewState,
  dataSourceLabel,
  EMPTY_SIGNAL_FILTERS,
  filterSignalRows,
  isLiveBrokerCatalogue,
  lastUpdatedCopy,
  MARKET_UNIVERSE_QUERY_KEY,
  mergeCatalogueRows,
  mergeResearchSignalFields,
  presentAssetClasses,
  presentField,
  RESEARCH_SIGNAL,
  SIGNALS_NOT_AUTHORIZATION,
  resolveConnectionPresentation,
  rowRegime,
  rowSession,
  scoreDisplay,
  signalAvailability,
  signalBoardDirection,
  signalFeedState,
  signalFeedStateLabel,
  signalFreshness,
  signalStrength,
  signalSummary,
  signalTimestampLabel,
  sortSignalRows,
  topResearchOpportunities,
  TRADER_POLL_MS,
  uniqueRowValues,
  unavailableSignalsTitle,
  UNIVERSE_POLL_MS,
  type SignalFilterState,
  type SignalSortKey,
} from "@/lib/trading/trader-ux";

const SORT_OPTIONS: Array<{ id: SignalSortKey; label: string }> = [
  { id: "strongest", label: "Strongest" },
  { id: "newest", label: "Newest" },
  { id: "opportunity", label: "Opportunity" },
  { id: "edge", label: "Edge" },
  { id: "risk_reward", label: "Risk/Reward" },
];

export function SignalsWorkspace() {
  const [filters, setFilters] = useState<SignalFilterState>(EMPTY_SIGNAL_FILTERS);
  const [sort, setSort] = useState<SignalSortKey>("strongest");
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);

  const sessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    retry: false,
    refetchInterval: TRADER_POLL_MS,
  });
  const session = asRecord(sessionQ.data);
  const connection = resolveConnectionPresentation(session);
  const liveCatalogue = isLiveBrokerCatalogue(session);
  const noBroker = connection.state === "BROKER_NOT_CONNECTED";
  const mismatch = connection.state === "ACCOUNT_SESSION_MISMATCH";

  const universeQ = useQuery({
    queryKey: MARKET_UNIVERSE_QUERY_KEY,
    queryFn: () => marketUniverseApi.snapshot(),
    enabled: connection.connected && !mismatch && liveCatalogue && !sessionQ.isLoading,
    retry: false,
    refetchInterval: UNIVERSE_POLL_MS,
  });

  const universe = asRecord(universeQ.data);
  const instruments = asList(universe.instruments).map(asRecord);
  const catalogue = catalogueViewState({
    connected: connection.connected,
    mismatch,
    liveBrokerSession: liveCatalogue,
    catalogueUnavailable: connection.catalogueUnavailable,
    snapshotFetched: universeQ.isFetched,
    snapshotError: Boolean(universeQ.isError),
    catalogueSource: universe.catalogue_source,
    instrumentCount: instruments.length,
  });
  const availability = signalAvailability(catalogue);
  const boardRows = asList(asRecord(universe.opportunity_board).rows).map(asRecord);
  const researchRows = asList(asRecord(universe.research_signals).signals).map(asRecord);
  const rows =
    availability === "LIVE_ROWS"
      ? mergeResearchSignalFields(mergeCatalogueRows(instruments, boardRows), researchRows)
      : [];

  const classes = useMemo(() => presentAssetClasses(rows), [rows]);
  const sessions = useMemo(() => uniqueRowValues(rows, rowSession), [rows]);
  const regimes = useMemo(() => uniqueRowValues(rows, rowRegime), [rows]);
  const confidences = useMemo(
    () =>
      uniqueRowValues(rows, (row) =>
        String(row.confidence_state || row.ai_confidence || "").trim().toUpperCase(),
      ),
    [rows],
  );
  const freshnessValues = useMemo(
    () => uniqueRowValues(rows, (row) => signalFreshness(row)),
    [rows],
  );

  const filtered = useMemo(() => filterSignalRows(rows, filters), [filters, rows]);
  const sorted = useMemo(() => sortSignalRows(filtered, sort), [filtered, sort]);

  const summary = signalSummary({
    availability,
    rows,
    instrumentCount: instruments.length,
    lastUpdate: universe.as_of,
  });
  const topOps = topResearchOpportunities(rows, availability, 4);
  const source = dataSourceLabel({
    liveBroker: liveCatalogue,
    catalogueSource: universe.catalogue_source ?? session.catalogue_source,
  });
  const unavailable = unavailableSignalsTitle({ noBroker, mismatch, catalogue });
  const feed = signalFeedState({
    loading: sessionQ.isLoading || universeQ.isLoading,
    noBroker,
    mismatch,
    snapshotError: Boolean(universeQ.isError),
    availability,
    rows,
  });
  const feedLabel = signalFeedStateLabel(feed);
  const updated = lastUpdatedCopy(universe.as_of);
  const feedTone =
    feed === "LIVE"
      ? "success"
      : feed === "STALE" || feed === "PARTIAL" || feed === "LOADING" || feed === "EMPTY"
        ? "warning"
        : "danger";

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        title="Signals"
        description="Real-time market intelligence. Research is not a trade authorization."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" asChild>
              <Link href="/markets">Markets</Link>
            </Button>
            <Button variant="secondary" size="sm" asChild>
              <Link href="/portfolio">Portfolio</Link>
            </Button>
          </div>
        }
      />

      <section aria-labelledby="signals-overview">
        <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="signals-overview" className="text-sm font-medium text-[var(--fg)]">
              Overview
            </h2>
            <p className="text-xs text-[var(--fg-subtle)]">
              {source}
              {updated ? ` · ${updated}` : ""}
              {` · ${feedLabel}`}
            </p>
          </div>
          <Badge tone={feedTone}>{feedLabel}</Badge>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <DeskMetric label="Active signals" value={summary.active} />
          <DeskMetric label="BUY opportunities" value={summary.buy} />
          <DeskMetric label="SELL opportunities" value={summary.sell} />
          <DeskMetric label="Strongest setup" value={summary.strongest} />
          <DeskMetric label="Markets covered" value={summary.markets} />
          <DeskMetric label="Last signal update" value={summary.lastUpdate} />
        </div>
      </section>

      {topOps.length > 0 ? (
        <section aria-labelledby="top-opportunities">
          <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
            <div>
              <h2 id="top-opportunities" className="text-sm font-medium text-[var(--fg)]">
                Top opportunities
              </h2>
              <p className="text-xs text-[var(--fg-subtle)]">
                {RESEARCH_SIGNAL} · {SIGNALS_NOT_AUTHORIZATION}
              </p>
            </div>
          </div>
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {topOps.map((row, i) => {
              const dir = signalBoardDirection(row);
              const symbol = str(row.broker_symbol || row.symbol, "—");
              const freshness = signalFreshness(row);
              return (
                <li key={`${symbol}-top-${i}`}>
                  <button
                    type="button"
                    onClick={() => setSelected(row)}
                    className="w-full rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] hover:border-[var(--accent)]"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="truncate font-semibold">{symbol}</p>
                      <Badge tone={directionTone(dir)}>{dir}</Badge>
                    </div>
                    <p className="mt-1 text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                      RESEARCH SIGNAL
                    </p>
                    <dl className="mt-2 grid grid-cols-3 gap-2 text-xs">
                      <div>
                        <dt className="text-[var(--fg-subtle)]">Opportunity</dt>
                        <dd className="tabular">{scoreDisplay(row.opportunity_score)}</dd>
                      </div>
                      <div>
                        <dt className="text-[var(--fg-subtle)]">Edge</dt>
                        <dd className="tabular">{scoreDisplay(row.directional_edge ?? row.edge)}</dd>
                      </div>
                      <div>
                        <dt className="text-[var(--fg-subtle)]">R/R</dt>
                        <dd className="tabular">{scoreDisplay(row.RR ?? row.rr)}</dd>
                      </div>
                    </dl>
                    <Badge tone={freshnessTone(freshness)} className="mt-2">
                      {freshness}
                    </Badge>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <Card>
        <CardContent className="min-w-0 space-y-4 pt-4">
          <h2 className="text-sm font-medium text-[var(--fg)]">All signals</h2>
          {sessionQ.isLoading ? (
            <DeskSkeleton rows={6} />
          ) : noBroker || mismatch || availability === "UNAVAILABLE" ? (
            <DeskEmpty
              icon={Radar}
              title={unavailable.title}
              description={unavailable.description}
              actionLabel="Connect Broker"
              actionHref="/broker"
            />
          ) : availability === "NOT_READY" || universeQ.isLoading ? (
            <DeskSkeleton rows={6} />
          ) : availability === "LIVE_EMPTY" ? (
            <DeskEmpty
              icon={Activity}
              title="No signals found"
              description="The live broker catalogue was queried. No ranked research signals are available right now."
            />
          ) : (
            <>
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Direction">
                  {(["ALL", "BUY", "SELL", "WATCH"] as const).map((dir) => (
                    <FilterChip
                      key={dir}
                      active={filters.direction === dir}
                      onClick={() => setFilters((f) => ({ ...f, direction: dir }))}
                    >
                      {dir}
                    </FilterChip>
                  ))}
                </div>
                {classes.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5" role="group" aria-label="Asset class">
                    <FilterChip
                      active={filters.assetClass === "ALL"}
                      onClick={() => setFilters((f) => ({ ...f, assetClass: "ALL" }))}
                    >
                      All classes
                    </FilterChip>
                    {classes.map((cls) => (
                      <FilterChip
                        key={cls}
                        active={filters.assetClass === cls}
                        onClick={() => setFilters((f) => ({ ...f, assetClass: cls }))}
                      >
                        {cls}
                      </FilterChip>
                    ))}
                  </div>
                ) : null}
                {sessions.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5" role="group" aria-label="Session">
                    <FilterChip
                      active={filters.session === "ALL"}
                      onClick={() => setFilters((f) => ({ ...f, session: "ALL" }))}
                    >
                      All sessions
                    </FilterChip>
                    {sessions.map((item) => (
                      <FilterChip
                        key={item}
                        active={filters.session === item}
                        onClick={() => setFilters((f) => ({ ...f, session: item }))}
                      >
                        {item}
                      </FilterChip>
                    ))}
                  </div>
                ) : null}
                {regimes.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5" role="group" aria-label="Regime">
                    <FilterChip
                      active={filters.regime === "ALL"}
                      onClick={() => setFilters((f) => ({ ...f, regime: "ALL" }))}
                    >
                      All regimes
                    </FilterChip>
                    {regimes.map((item) => (
                      <FilterChip
                        key={item}
                        active={filters.regime === item}
                        onClick={() => setFilters((f) => ({ ...f, regime: item }))}
                      >
                        {item}
                      </FilterChip>
                    ))}
                  </div>
                ) : null}
                {confidences.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5" role="group" aria-label="Strength">
                    <FilterChip
                      active={filters.confidence === "ALL"}
                      onClick={() => setFilters((f) => ({ ...f, confidence: "ALL" }))}
                    >
                      All strength
                    </FilterChip>
                    {confidences.map((item) => (
                      <FilterChip
                        key={item}
                        active={filters.confidence === item}
                        onClick={() => setFilters((f) => ({ ...f, confidence: item }))}
                      >
                        {item}
                      </FilterChip>
                    ))}
                  </div>
                ) : null}
                {freshnessValues.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5" role="group" aria-label="Freshness">
                    <FilterChip
                      active={filters.freshness === "ALL"}
                      onClick={() => setFilters((f) => ({ ...f, freshness: "ALL" }))}
                    >
                      All freshness
                    </FilterChip>
                    {freshnessValues.map((item) => (
                      <FilterChip
                        key={item}
                        active={filters.freshness === item}
                        onClick={() => setFilters((f) => ({ ...f, freshness: item }))}
                      >
                        {item}
                      </FilterChip>
                    ))}
                  </div>
                ) : null}
                <div className="flex flex-wrap items-center gap-2">
                  <label htmlFor="signal-sort" className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                    Sort
                  </label>
                  <select
                    id="signal-sort"
                    className="h-8 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-sm text-[var(--fg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                    value={sort}
                    onChange={(e) => setSort(e.target.value as SignalSortKey)}
                  >
                    {SORT_OPTIONS.map((opt) => (
                      <option key={opt.id} value={opt.id}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {sorted.length === 0 ? (
                <DeskEmpty
                  icon={Activity}
                  title="No matching signals"
                  description="No signals match the current filters."
                />
              ) : (
                <>
                  <div className="hidden min-w-0 overflow-x-auto md:block">
                    <table className="w-full min-w-[860px] text-left text-sm" aria-label="Signals">
                      <thead>
                        <tr className="border-b border-[var(--border)] text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                          <th className="py-2 pr-3 font-medium" scope="col">Symbol</th>
                          <th className="py-2 pr-3 font-medium" scope="col">Direction</th>
                          <th className="py-2 pr-3 font-medium" scope="col">Opportunity</th>
                          <th className="py-2 pr-3 font-medium" scope="col">Edge</th>
                          <th className="py-2 pr-3 font-medium" scope="col">R/R</th>
                          <th className="py-2 pr-3 font-medium" scope="col">Strength</th>
                          <th className="py-2 pr-3 font-medium" scope="col">Session</th>
                          <th className="py-2 pr-3 font-medium" scope="col">Regime</th>
                          <th className="py-2 pr-3 font-medium" scope="col">Class</th>
                          <th className="py-2 pr-3 font-medium" scope="col">Timestamp</th>
                          <th className="py-2 pr-3 font-medium" scope="col">Freshness</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sorted.map((row, i) => {
                          const dir = signalBoardDirection(row);
                          const symbol = str(row.broker_symbol || row.symbol, "—");
                          const freshness = signalFreshness(row);
                          return (
                            <tr key={`${symbol}-row-${i}`} className="border-b border-[var(--border)]">
                              <td className="py-2 pr-3">
                                <button
                                  type="button"
                                  onClick={() => setSelected(row)}
                                  className="font-medium text-[var(--fg)] underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                                >
                                  {symbol}
                                </button>
                              </td>
                              <td className="py-2 pr-3">
                                <Badge tone={directionTone(dir)}>{dir}</Badge>
                              </td>
                              <td className="py-2 pr-3 tabular">{scoreDisplay(row.opportunity_score)}</td>
                              <td className="py-2 pr-3 tabular">{scoreDisplay(row.directional_edge ?? row.edge)}</td>
                              <td className="py-2 pr-3 tabular">{scoreDisplay(row.RR ?? row.rr)}</td>
                              <td className="py-2 pr-3 tabular">{signalStrength(row)}</td>
                              <td className="py-2 pr-3">{presentField(row.session)}</td>
                              <td className="py-2 pr-3">{presentField(rowRegime(row))}</td>
                              <td className="py-2 pr-3">{presentField(row.asset_class)}</td>
                              <td className="py-2 pr-3 text-xs text-[var(--fg-muted)]">{signalTimestampLabel(row)}</td>
                              <td className="py-2 pr-3">
                                <Badge tone={freshnessTone(freshness)}>{freshness}</Badge>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <ul className="grid gap-3 md:hidden" aria-label="Signals">
                    {sorted.map((row, i) => {
                      const dir = signalBoardDirection(row);
                      const symbol = str(row.broker_symbol || row.symbol, "—");
                      const freshness = signalFreshness(row);
                      return (
                        <li key={`${symbol}-${i}`}>
                          <button
                            type="button"
                            onClick={() => setSelected(row)}
                            className="w-full rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] p-4 text-left transition hover:border-[var(--accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="min-w-0">
                                <p className="truncate font-semibold text-[var(--fg)]">{symbol}</p>
                                <p className="text-xs text-[var(--fg-subtle)]">
                                  {presentField(row.asset_class)} · {presentField(row.session)}
                                </p>
                              </div>
                              <div className="flex flex-wrap items-center gap-1.5">
                                <Badge tone={directionTone(dir)}>{dir}</Badge>
                                <Badge tone={freshnessTone(freshness)}>{freshness}</Badge>
                              </div>
                            </div>
                            <dl className="mt-3 grid grid-cols-3 gap-2 text-sm">
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">Opportunity</dt>
                                <dd className="tabular">{scoreDisplay(row.opportunity_score)}</dd>
                              </div>
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">Edge</dt>
                                <dd className="tabular">{scoreDisplay(row.directional_edge ?? row.edge)}</dd>
                              </div>
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">R/R</dt>
                                <dd className="tabular">{scoreDisplay(row.RR ?? row.rr)}</dd>
                              </div>
                            </dl>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Dialog open={selected != null} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="w-[min(96vw,720px)]" aria-describedby={undefined}>
          {selected ? <IntelligenceDetail row={selected} kind="signal" /> : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
