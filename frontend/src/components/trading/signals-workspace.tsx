"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Radar, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { DeskEmpty, DeskMetric, DeskSkeleton } from "@/components/desk/primitives";
import { FilterChip } from "@/components/trading/filter-chip";
import { IntelligenceDetail, directionTone, freshnessTone } from "@/components/trading/intelligence-detail";
import { marketUniverseApi, signalCenterApi, tradingSessionApi } from "@/lib/api/endpoints";
import { asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";
import {
  accountConnectionHint,
  analysisDeskStatusLabel,
  ASSET_CLASS_ORDER,
  EMPTY_SIGNAL_FILTERS,
  filterSignalRows,
  knownUniverseCountLabel,
  lastUpdatedCopy,
  MARKET_UNIVERSE_QUERY_KEY,
  normalizeSignalCenterPayload,
  presentField,
  presentLevel,
  presentPrice,
  RESEARCH_INDEPENDENT_COPY,
  RESEARCH_SIGNAL,
  researchAvailabilityAsCatalogue,
  researchSignalsEmptyCopy,
  resolveAnalysisDeskStatus,
  resolveConnectionPresentation,
  rowRegime,
  rowSession,
  scoreDisplay,
  SIGNAL_CENTER_QUERY_KEY,
  SIGNALS_NOT_AUTHORIZATION,
  signalBoardDirection,
  signalFreshness,
  signalFreshnessLabel,
  signalStrength,
  signalSummary,
  signalTimestampLabel,
  sortSignalRows,
  topResearchOpportunities,
  TRADER_POLL_MS,
  uniqueRowValues,
  type AnalysisDeskStatus,
  type SignalFilterState,
  type SignalSortKey,
} from "@/lib/trading/trader-ux";

const SORT_OPTIONS: Array<{ id: SignalSortKey; label: string }> = [
  { id: "strongest", label: "Research rank" },
  { id: "opportunity", label: "Opportunity" },
  { id: "edge", label: "Edge" },
  { id: "newest", label: "Newest" },
];

const MARKET_CLASS_FILTERS = ["ALL", ...ASSET_CLASS_ORDER] as const;

function analysisTone(
  status: AnalysisDeskStatus,
): "success" | "warning" | "danger" | "neutral" | "accent" {
  if (status === "ANALYSIS_READY") return "success";
  if (status === "ANALYSIS_RUNNING") return "accent";
  if (status === "NO_ACTIVE_SIGNALS" || status === "DATA_PARTIAL" || status === "DATA_STALE") {
    return "warning";
  }
  return "danger";
}

function researchWorkerTone(
  status: string,
): "success" | "warning" | "danger" | "neutral" | "accent" {
  if (status === "RUNNING") return "accent";
  if (status === "DEGRADED") return "warning";
  if (status === "STOPPED" || status === "UNAVAILABLE") return "danger";
  return "neutral";
}

export function SignalsWorkspace() {
  const qc = useQueryClient();
  const [filters, setFilters] = useState<SignalFilterState>(EMPTY_SIGNAL_FILTERS);
  const [sort, setSort] = useState<SignalSortKey>("strongest");
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const sessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    retry: false,
    refetchInterval: TRADER_POLL_MS,
  });
  const session = asRecord(sessionQ.data);
  const connection = resolveConnectionPresentation(session);
  const accountHint = accountConnectionHint(connection);

  const signalsQ = useQuery({
    queryKey: SIGNAL_CENTER_QUERY_KEY,
    queryFn: () => signalCenterApi.list({ enabled_only: false }),
    retry: false,
    refetchInterval: TRADER_POLL_MS,
  });

  const normalized = useMemo(
    () =>
      normalizeSignalCenterPayload(
        signalsQ.isError ? null : asRecord(signalsQ.data),
      ),
    [signalsQ.data, signalsQ.isError],
  );
  const availability = signalsQ.isError
    ? ("UNAVAILABLE" as const)
    : normalized.availability;
  const catalogueAvailability = researchAvailabilityAsCatalogue(availability);
  const signalRows = normalized.rows;
  const researchHealth = normalized.researchAnalysis ?? {};
  const workerStatus = String(researchHealth.status || "UNKNOWN").toUpperCase();

  const sessions = useMemo(() => uniqueRowValues(signalRows, rowSession), [signalRows]);
  const regimes = useMemo(() => uniqueRowValues(signalRows, rowRegime), [signalRows]);

  const filtered = useMemo(() => filterSignalRows(signalRows, filters), [filters, signalRows]);
  const sorted = useMemo(() => sortSignalRows(filtered, sort), [filtered, sort]);

  const summary = signalSummary({
    availability: catalogueAvailability,
    rows: signalRows,
    instrumentCount:
      normalized.universeSize != null ? normalized.universeSize : signalRows.length,
    lastUpdate: normalized.asOf,
  });
  const topOps = topResearchOpportunities(signalRows, catalogueAvailability, 4);
  const analysisStatus = resolveAnalysisDeskStatus({
    loading: signalsQ.isLoading || signalsQ.isFetching,
    fetchError: Boolean(signalsQ.isError),
    availability,
    rows: signalRows,
    fabricatedBlocked: normalized.fabricatedBlocked,
    asOf: normalized.asOf,
    universeSize: normalized.universeSize,
  });
  const analysisLabel = analysisDeskStatusLabel(analysisStatus);
  const updated = lastUpdatedCopy(normalized.asOf);
  const emptyCopy = researchSignalsEmptyCopy({
    fetchError: Boolean(signalsQ.isError),
    fabricatedBlocked: normalized.fabricatedBlocked,
    empty: true,
    universeSize: normalized.universeSize,
  });
  const marketsAnalyzed = knownUniverseCountLabel(
    normalized.universeSize,
    normalized.countConfirmed && !signalsQ.isError,
  );

  async function refreshAnalysis() {
    setRefreshing(true);
    try {
      // Research refresh only — never starts live trading / OMS.
      await marketUniverseApi.refresh().catch(() => null);
      await qc.invalidateQueries({ queryKey: MARKET_UNIVERSE_QUERY_KEY });
      await signalsQ.refetch();
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="min-w-0 space-y-5">
      <PageHeader
        title="Signals"
        description="Global market intelligence — research analysis across the supported broker universe. Not a trade authorization."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={signalsQ.isFetching || refreshing}
              onClick={() => void refreshAnalysis()}
            >
              <RefreshCw
                className={cn(
                  "h-3.5 w-3.5",
                  (signalsQ.isFetching || refreshing) && "animate-spin",
                )}
              />
              Refresh analysis
            </Button>
            <Button variant="secondary" size="sm" asChild>
              <Link href="/markets">View markets</Link>
            </Button>
          </div>
        }
      />

      <section
        aria-label="Research, broker, and live trading status"
        aria-live="polite"
        className="grid gap-2 sm:grid-cols-3"
      >
        <div className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Research
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Badge tone={analysisTone(analysisStatus)}>{analysisLabel}</Badge>
            <Badge tone={researchWorkerTone(workerStatus)}>
              ENGINE {workerStatus === "UNKNOWN" ? "—" : workerStatus}
            </Badge>
          </div>
          <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
            Broker not required for research analysis
          </p>
        </div>
        <div className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Broker
          </p>
          <div className="mt-1.5">
            <Badge
              tone={
                accountHint.detail === "CONNECTED"
                  ? "success"
                  : accountHint.detail === "SESSION MISMATCH"
                    ? "danger"
                    : "neutral"
              }
            >
              {accountHint.detail === "CONNECTED"
                ? "CONNECTED"
                : accountHint.detail === "SESSION MISMATCH"
                  ? "SESSION MISMATCH"
                  : "NOT CONNECTED"}
            </Badge>
          </div>
          <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
            Ownership session — independent of research
          </p>
        </div>
        <div className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Live trading
          </p>
          <div className="mt-1.5">
            <Badge tone="neutral">NOT AUTHORIZED</Badge>
          </div>
          <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
            {SIGNALS_NOT_AUTHORIZATION}
          </p>
        </div>
      </section>

      {updated ? (
        <p className="text-xs text-[var(--fg-subtle)]">Last analysis update · {updated}</p>
      ) : null}

      <p className="text-sm text-[var(--fg-muted)]">{RESEARCH_INDEPENDENT_COPY}</p>

      <section aria-labelledby="market-universe">
        <div className="mb-2">
          <h2 id="market-universe" className="text-sm font-medium text-[var(--fg)]">
            Global market universe
          </h2>
          <p className="text-xs text-[var(--fg-subtle)]">
            Discovered from the live broker catalogue — never invented
          </p>
        </div>
        <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Market class">
          {MARKET_CLASS_FILTERS.map((cls) => (
            <FilterChip
              key={cls}
              active={filters.assetClass === cls}
              onClick={() => setFilters((f) => ({ ...f, assetClass: cls }))}
            >
              {cls}
            </FilterChip>
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <DeskMetric label="Supported instruments" value={marketsAnalyzed} />
          <DeskMetric
            label="Analyzed"
            value={
              researchHealth.instruments_analyzed != null
                ? String(researchHealth.instruments_analyzed)
                : marketsAnalyzed
            }
          />
          <DeskMetric
            label="Coverage"
            value={
              researchHealth.coverage_pct != null
                ? `${researchHealth.coverage_pct}%`
                : "—"
            }
          />
          <DeskMetric label="Active signals" value={summary.active} />
          <DeskMetric label="BUY" value={summary.buy} />
          <DeskMetric label="SELL" value={summary.sell} />
        </div>
      </section>

      <section aria-labelledby="signals-overview">
        <h2 id="signals-overview" className="mb-2 text-sm font-medium text-[var(--fg)]">
          Global research
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <DeskMetric label="Strongest opportunity" value={summary.strongest} />
          <DeskMetric label="Strongest edge" value={summary.strongestEdge} />
          <DeskMetric label="Markets analyzed" value={marketsAnalyzed} />
          <DeskMetric label="Desk status" value={analysisLabel} />
        </div>
      </section>

      {topOps.length > 0 ? (
        <section aria-labelledby="top-opportunities">
          <div className="mb-2">
            <h2 id="top-opportunities" className="text-sm font-medium text-[var(--fg)]">
              Top opportunities
            </h2>
            <p className="text-xs text-[var(--fg-subtle)]">
              {RESEARCH_SIGNAL} · {SIGNALS_NOT_AUTHORIZATION}
            </p>
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
                      <div className="min-w-0">
                        <p className="truncate font-semibold">{symbol}</p>
                        <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                          {presentField(row.asset_class)} · RESEARCH SIGNAL
                        </p>
                      </div>
                      <Badge tone={directionTone(dir)}>{dir}</Badge>
                    </div>
                    <dl className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                      <div>
                        <dt className="text-[var(--fg-subtle)]">Opp</dt>
                        <dd className="tabular">{scoreDisplay(row.opportunity_score)}</dd>
                      </div>
                      <div>
                        <dt className="text-[var(--fg-subtle)]">Edge</dt>
                        <dd className="tabular">{scoreDisplay(row.directional_edge ?? row.edge)}</dd>
                      </div>
                      <div>
                        <dt className="text-[var(--fg-subtle)]">Rank</dt>
                        <dd className="tabular">{scoreDisplay(row.research_rank_score)}</dd>
                      </div>
                      <div>
                        <dt className="text-[var(--fg-subtle)]">Price</dt>
                        <dd className="tabular">
                          {presentPrice(row.price ?? row.mid ?? row.bid)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-[var(--fg-subtle)]">Entry</dt>
                        <dd className="tabular">
                          {presentLevel(row.entry ?? row.entry_candidate, "Entry")}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-[var(--fg-subtle)]">SL</dt>
                        <dd className="tabular">
                          {presentLevel(row.stop_loss ?? row.SL_candidate, "SL")}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-[var(--fg-subtle)]">TP</dt>
                        <dd className="tabular">
                          {presentLevel(row.take_profit ?? row.TP_candidate, "TP")}
                        </dd>
                      </div>
                    </dl>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <Badge tone={freshnessTone(freshness)}>
                        {signalFreshnessLabel(freshness)}
                      </Badge>
                      <span className="truncate text-[11px] text-[var(--fg-subtle)]">
                        {[presentField(row.session), presentField(rowRegime(row))]
                          .filter((part) => part && part !== "Not available")
                          .join(" · ")}
                      </span>
                    </div>
                    <p className="mt-2 text-[11px] font-medium text-[var(--accent)]">
                      Why this signal? →
                    </p>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <Card>
        <CardContent className="min-w-0 space-y-4 pt-4">
          <h2 className="text-sm font-medium text-[var(--fg)]">Signal feed</h2>
          {signalsQ.isLoading ? (
            <DeskSkeleton rows={6} />
          ) : signalsQ.isError || availability === "UNAVAILABLE" ? (
            <DeskEmpty
              icon={Radar}
              title={emptyCopy.title}
              description={emptyCopy.description}
            />
          ) : availability === "NOT_READY" ? (
            <DeskSkeleton rows={6} />
          ) : availability === "LIVE_EMPTY" || signalRows.length === 0 ? (
            <DeskEmpty
              icon={Activity}
              title={emptyCopy.title}
              description={emptyCopy.description}
            />
          ) : (
            <>
              <div className="flex flex-col gap-3">
                <Input
                  value={filters.q}
                  onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
                  placeholder="Search symbol"
                  aria-label="Search signals"
                />
                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Direction">
                  {(["ALL", "BUY", "SELL"] as const).map((dir) => (
                    <FilterChip
                      key={dir}
                      active={filters.direction === dir}
                      onClick={() => setFilters((f) => ({ ...f, direction: dir }))}
                    >
                      {dir}
                    </FilterChip>
                  ))}
                </div>
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
                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Freshness">
                  {(
                    [
                      "ALL",
                      "LIVE",
                      "RECENT",
                      "STALE",
                      "PARTIAL",
                      "UNAVAILABLE",
                    ] as const
                  ).map((fresh) => (
                    <FilterChip
                      key={fresh}
                      active={filters.freshness === fresh}
                      onClick={() => setFilters((f) => ({ ...f, freshness: fresh }))}
                    >
                      {fresh === "ALL"
                        ? "All freshness"
                        : fresh === "LIVE"
                          ? "LIVE DATA"
                          : fresh === "UNAVAILABLE"
                            ? "DATA UNAVAILABLE"
                            : fresh}
                    </FilterChip>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <label
                    htmlFor="signal-sort"
                    className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]"
                  >
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
                    <table
                      className="w-full min-w-[1100px] text-left text-sm"
                      aria-label="Signals"
                    >
                      <thead>
                        <tr className="border-b border-[var(--border)] text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                          <th className="py-2 pr-3 font-medium" scope="col">
                            Symbol
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            Class
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            Direction
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            Opportunity
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            Edge
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            R/R
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            Strength
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            Rank
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            Session
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            Regime
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            Price
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            Entry
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            SL
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            TP
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            Timestamp
                          </th>
                          <th className="py-2 pr-3 font-medium" scope="col">
                            Freshness
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {sorted.map((row, i) => {
                          const dir = signalBoardDirection(row);
                          const symbol = str(row.broker_symbol || row.symbol, "—");
                          const freshness = signalFreshness(row);
                          return (
                            <tr
                              key={`${symbol}-row-${i}`}
                              className="border-b border-[var(--border)]"
                            >
                              <td className="py-2 pr-3">
                                <button
                                  type="button"
                                  onClick={() => setSelected(row)}
                                  className="font-medium text-[var(--fg)] underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                                >
                                  {symbol}
                                </button>
                              </td>
                              <td className="py-2 pr-3">{presentField(row.asset_class)}</td>
                              <td className="py-2 pr-3">
                                <Badge tone={directionTone(dir)}>{dir}</Badge>
                              </td>
                              <td className="py-2 pr-3 tabular">
                                {scoreDisplay(row.opportunity_score)}
                              </td>
                              <td className="py-2 pr-3 tabular">
                                {scoreDisplay(row.directional_edge ?? row.edge)}
                              </td>
                              <td className="py-2 pr-3 tabular">
                                {scoreDisplay(row.RR ?? row.rr)}
                              </td>
                              <td className="py-2 pr-3 tabular">{signalStrength(row)}</td>
                              <td className="py-2 pr-3 tabular">
                                {scoreDisplay(row.research_rank_score)}
                              </td>
                              <td className="py-2 pr-3">{presentField(row.session)}</td>
                              <td className="py-2 pr-3">{presentField(rowRegime(row))}</td>
                              <td className="py-2 pr-3 tabular">
                                {presentPrice(row.price ?? row.mid ?? row.bid)}
                              </td>
                              <td className="py-2 pr-3 tabular">
                                {presentLevel(row.entry ?? row.entry_candidate, "Entry")}
                              </td>
                              <td className="py-2 pr-3 tabular">
                                {presentLevel(row.stop_loss ?? row.SL_candidate, "SL")}
                              </td>
                              <td className="py-2 pr-3 tabular">
                                {presentLevel(row.take_profit ?? row.TP_candidate, "TP")}
                              </td>
                              <td className="py-2 pr-3 text-xs text-[var(--fg-muted)]">
                                {signalTimestampLabel(row)}
                              </td>
                              <td className="py-2 pr-3">
                                <Badge tone={freshnessTone(freshness)}>
                                  {signalFreshnessLabel(freshness)}
                                </Badge>
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
                                <p className="truncate font-semibold text-[var(--fg)]">
                                  {symbol}
                                </p>
                                <p className="text-xs text-[var(--fg-subtle)]">
                                  {presentField(row.asset_class)} ·{" "}
                                  {presentField(row.session)}
                                </p>
                              </div>
                              <div className="flex flex-wrap items-center gap-1.5">
                                <Badge tone={directionTone(dir)}>{dir}</Badge>
                                <Badge tone={freshnessTone(freshness)}>
                                  {signalFreshnessLabel(freshness)}
                                </Badge>
                              </div>
                            </div>
                            <dl className="mt-3 grid grid-cols-3 gap-2 text-sm">
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">
                                  Opportunity
                                </dt>
                                <dd className="tabular">
                                  {scoreDisplay(row.opportunity_score)}
                                </dd>
                              </div>
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">
                                  Edge
                                </dt>
                                <dd className="tabular">
                                  {scoreDisplay(row.directional_edge ?? row.edge)}
                                </dd>
                              </div>
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">
                                  Rank
                                </dt>
                                <dd className="tabular">
                                  {scoreDisplay(row.research_rank_score)}
                                </dd>
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
