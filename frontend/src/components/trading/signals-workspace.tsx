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
import { Dialog, SheetContent } from "@/components/ui/dialog";
import { DeskEmpty, DeskMetric, DeskSkeleton } from "@/components/desk/primitives";
import { FilterChip } from "@/components/trading/filter-chip";
import { IntelligenceDetail, directionTone, freshnessTone } from "@/components/trading/intelligence-detail";
import { marketUniverseApi, signalCenterApi, tradingSessionApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";
import {
  accountConnectionHint,
  analysisDeskStatusLabel,
  ASSET_CLASS_ORDER,
  cataloguePageSlice,
  EMPTY_SIGNAL_FILTERS,
  filterSignalRows,
  knownUniverseCountLabel,
  lastUpdatedCopy,
  MARKET_PAGE_SIZE,
  MARKET_UNIVERSE_QUERY_KEY,
  marketStateBucket,
  normalizeAssetClass,
  normalizeSignalCenterPayload,
  presentField,
  presentLevel,
  presentPrice,
  RESEARCH_INDEPENDENT_COPY,
  RESEARCH_SIGNAL,
  researchAvailabilityAsCatalogue,
  researchCoverageLabel,
  researchDeskLiveTradingStatus,
  researchLifecycleCounts,
  researchLifecycleLabel,
  researchProgressCopy,
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
  signalWhyPreview,
  sortSignalRows,
  topResearchOpportunities,
  TRADER_POLL_MS,
  UNIVERSE_POLL_MS,
  uniqueRowValues,
  type AnalysisDeskStatus,
  type SignalFilterState,
  type SignalSortKey,
} from "@/lib/trading/trader-ux";

const SORT_OPTIONS: Array<{ id: SignalSortKey; label: string }> = [
  { id: "strongest", label: "Strongest" },
  { id: "newest", label: "Newest" },
  { id: "instrument", label: "Symbol" },
  { id: "asset_class", label: "Asset class" },
];

const MARKET_CLASS_FILTERS = ["ALL", ...ASSET_CLASS_ORDER] as const;
const SIGNAL_FEED_PAGE_SIZE = 40;
const STATUS_FILTERS = [
  { id: "ALL", label: "All status" },
  { id: "ACTIVE", label: "Active" },
  { id: "RECENT", label: "Recent" },
  { id: "CLOSED", label: "Closed" },
  { id: "UNAVAILABLE", label: "Unavailable" },
] as const;

type StatusFilterId = (typeof STATUS_FILTERS)[number]["id"];

function CompactSelect({
  id,
  label,
  value,
  onChange,
  options,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ id: string; label: string }>;
}) {
  return (
    <label className="flex min-w-[9.5rem] flex-1 flex-col gap-1 text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
      {label}
      <select
        id={id}
        className="h-9 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface)] px-2 text-sm font-medium normal-case tracking-normal text-[var(--fg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((opt) => (
          <option key={opt.id} value={opt.id}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}

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
  const [statusFilter, setStatusFilter] = useState<StatusFilterId>("ALL");
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [feedLimit, setFeedLimit] = useState(SIGNAL_FEED_PAGE_SIZE);
  const [universePage, setUniversePage] = useState(1);

  const sessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    retry: false,
    refetchInterval: TRADER_POLL_MS,
  });
  const session = asRecord(sessionQ.data);
  const connection = resolveConnectionPresentation(session);
  const accountHint = accountConnectionHint(connection);
  const liveTradingHint = researchDeskLiveTradingStatus(connection);

  const signalsQ = useQuery({
    queryKey: SIGNAL_CENTER_QUERY_KEY,
    queryFn: () => signalCenterApi.list({ enabled_only: false }),
    retry: false,
    refetchInterval: TRADER_POLL_MS,
  });

  const universeQ = useQuery({
    queryKey: MARKET_UNIVERSE_QUERY_KEY,
    queryFn: () => marketUniverseApi.snapshot(),
    retry: false,
    refetchInterval: UNIVERSE_POLL_MS,
  });
  const universeSnap = asRecord(universeQ.data);
  const universeInstruments = useMemo(() => {
    const rows = asList(universeSnap.instruments).map(asRecord);
    return rows.filter((row) => {
      const sym = str(row.broker_symbol || row.canonical_symbol || row.symbol, "");
      return Boolean(sym);
    });
  }, [universeSnap.instruments]);

  const filteredUniverse = useMemo(() => {
    return universeInstruments.filter((row) => {
      if (
        filters.assetClass !== "ALL" &&
        normalizeAssetClass(row.asset_class) !== filters.assetClass
      ) {
        return false;
      }
      if (
        filters.marketState !== "ALL" &&
        marketStateBucket(row) !== filters.marketState
      ) {
        return false;
      }
      const q = (filters.q || "").trim().toUpperCase();
      if (q) {
        const hay = `${str(row.broker_symbol || row.symbol, "")} ${str(row.asset_class, "")}`.toUpperCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [filters.assetClass, filters.marketState, filters.q, universeInstruments]);

  const universePageRows = useMemo(
    () => cataloguePageSlice(filteredUniverse, universePage, MARKET_PAGE_SIZE),
    [filteredUniverse, universePage],
  );
  const universePageCount = Math.max(
    1,
    Math.ceil(filteredUniverse.length / MARKET_PAGE_SIZE),
  );

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

  const filtered = useMemo(() => {
    const next: SignalFilterState = { ...filters };
    if (statusFilter === "ACTIVE") next.freshness = "LIVE";
    else if (statusFilter === "RECENT") next.freshness = "RECENT";
    else if (statusFilter === "CLOSED") next.marketState = "CLOSED";
    else if (statusFilter === "UNAVAILABLE") next.freshness = "UNAVAILABLE";
    return filterSignalRows(signalRows, next);
  }, [filters, signalRows, statusFilter]);
  const sorted = useMemo(() => sortSignalRows(filtered, sort), [filtered, sort]);
  const feedRows = useMemo(() => sorted.slice(0, feedLimit), [feedLimit, sorted]);

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
  const coverageLabel = researchCoverageLabel(researchHealth);
  const progressCopy = researchProgressCopy(researchHealth);
  const discoveredLabel =
    researchHealth.instruments_discovered != null
      ? String(researchHealth.instruments_discovered)
      : marketsAnalyzed;
  const eligibleLabel =
    researchHealth.instruments_eligible != null
      ? String(researchHealth.instruments_eligible)
      : "—";
  const analyzedLabel =
    researchHealth.instruments_analyzed != null
      ? String(researchHealth.instruments_analyzed)
      : "—";
  const failedLabel =
    researchHealth.instruments_failed != null
      ? String(researchHealth.instruments_failed)
      : "—";
  const unavailableLabel =
    researchHealth.instruments_unavailable != null
      ? String(researchHealth.instruments_unavailable)
      : "—";
  const coverageState = String(researchHealth.coverage_state || "").toUpperCase();
  const lifecycle = researchLifecycleCounts(universeInstruments);
  const assetClassCounts =
    researchHealth.asset_class_counts &&
    typeof researchHealth.asset_class_counts === "object"
      ? (researchHealth.asset_class_counts as Record<string, unknown>)
      : {};

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
        eyebrow="Signals"
        title="Global Market Signals"
        description="Research-backed market intelligence. Research intelligence is independent of your MT5 connection."
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
        aria-label="Global research independence"
        className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3"
      >
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            GLOBAL RESEARCH
          </p>
          <Badge
            tone={
              signalsQ.isError || availability === "UNAVAILABLE"
                ? "danger"
                : "success"
            }
          >
            {signalsQ.isError || availability === "UNAVAILABLE"
              ? "UNAVAILABLE"
              : "ACTIVE"}
          </Badge>
        </div>
        <p className="mt-2 max-w-3xl text-sm text-[var(--fg-muted)]">
          {RESEARCH_INDEPENDENT_COPY} You can view signals without connecting a broker.
          Live trading remains a separate, explicitly authorized step.
        </p>
        <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
          <div>
            <dt className="text-[var(--fg-subtle)]">Broker connection</dt>
            <dd>
              {accountHint.detail === "CONNECTED"
                ? "Connected"
                : accountHint.detail === "SESSION MISMATCH"
                  ? "Session mismatch"
                  : "Not connected"}
            </dd>
          </div>
          <div>
            <dt className="text-[var(--fg-subtle)]">Research</dt>
            <dd>
              {signalsQ.isError || availability === "UNAVAILABLE"
                ? "Unavailable"
                : "Available"}
            </dd>
          </div>
          <div>
            <dt className="text-[var(--fg-subtle)]">Live trading</dt>
            <dd>{liveTradingHint.detail}</dd>
          </div>
        </dl>
      </section>

      <section
        aria-label="Global research status bar"
        aria-live="polite"
        className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7"
      >
        <DeskMetric label="Analysis" value={analysisLabel} />
        <DeskMetric label="Universe" value={discoveredLabel} />
        <DeskMetric label="Analyzed" value={analyzedLabel} />
        <DeskMetric label="Coverage" value={coverageLabel} />
        <DeskMetric
          label="Last update"
          value={updated || "—"}
        />
        <DeskMetric
          label="Broker status"
          value={
            accountHint.detail === "CONNECTED"
              ? "CONNECTED"
              : accountHint.detail === "SESSION MISMATCH"
                ? "MISMATCH"
                : "NOT CONNECTED"
          }
        />
        <DeskMetric
          label="Research mode"
          value={workerStatus === "UNKNOWN" ? "ADVISORY" : workerStatus}
        />
      </section>

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
            {coverageState && coverageState !== "UNKNOWN" ? (
              <Badge tone={coverageState === "READY" ? "success" : "warning"}>
                {coverageState}
              </Badge>
            ) : null}
          </div>
          <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
            {progressCopy || "Broker not required for research analysis"}
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
            <Badge
              tone={
                liveTradingHint.state === "LIVE_TRADING_UNAVAILABLE"
                  ? "neutral"
                  : "warning"
              }
            >
              {liveTradingHint.label}
            </Badge>
          </div>
          <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
            {liveTradingHint.detail}
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
            Eligible coverage is the subset research can analyze. Full catalogue coverage is
            every discovered instrument. QuantForg never claims 100% global coverage.
          </p>
        </div>
        <div className="mb-3 max-w-xs">
          <CompactSelect
            id="universe-class"
            label="Asset class"
            value={filters.assetClass}
            onChange={(value) => {
              setUniversePage(1);
              setFilters((f) => ({ ...f, assetClass: value }));
            }}
            options={MARKET_CLASS_FILTERS.map((cls) => ({
              id: cls,
              label: cls === "ALL" ? "All classes" : cls,
            }))}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          <DeskMetric label="Discovered" value={discoveredLabel} />
          <DeskMetric label="Eligible" value={eligibleLabel} />
          <DeskMetric label="Analyzed" value={analyzedLabel} />
          <DeskMetric label="Queued" value={String(lifecycle.queued)} />
          <DeskMetric label="Market closed" value={String(lifecycle.closed)} />
          <DeskMetric label="Unavailable" value={unavailableLabel} />
          <DeskMetric label="Failed" value={failedLabel} />
          <DeskMetric label="Coverage" value={coverageLabel} />
        </div>
        {Object.keys(assetClassCounts).length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-2" aria-label="Asset class distribution">
            {ASSET_CLASS_ORDER.map((cls) => {
              const raw = assetClassCounts[cls];
              if (raw == null || raw === "UNAVAILABLE") return null;
              return (
                <span
                  key={cls}
                  className="rounded-md border border-[var(--border)] px-2 py-1 text-[11px] text-[var(--fg-muted)]"
                >
                  {cls} · {String(raw)}
                </span>
              );
            })}
          </div>
        ) : null}
      </section>

      <section aria-labelledby="signals-overview">
        <h2 id="signals-overview" className="mb-2 text-sm font-medium text-[var(--fg)]">
          Market bias & research
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <DeskMetric label="Strongest opportunity" value={summary.strongest} />
          <DeskMetric label="Strongest edge" value={summary.strongestEdge} />
          <DeskMetric label="Supported instruments" value={marketsAnalyzed} />
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
                      <div>
                        <dt className="text-[var(--fg-subtle)]">RR</dt>
                        <dd className="tabular">{scoreDisplay(row.RR ?? row.rr)}</dd>
                      </div>
                      <div>
                        <dt className="text-[var(--fg-subtle)]">Regime</dt>
                        <dd>{presentField(rowRegime(row))}</dd>
                      </div>
                    </dl>
                    <p className="mt-2 line-clamp-2 text-[11px] text-[var(--fg-muted)]">
                      {signalWhyPreview(row)}
                    </p>
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
                    <p className="mt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--accent)]">
                      Why this signal
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
                  {(["ALL", "BUY", "SELL", "NEUTRAL"] as const).map((dir) => (
                    <FilterChip
                      key={dir}
                      active={filters.direction === dir}
                      onClick={() => setFilters((f) => ({ ...f, direction: dir }))}
                    >
                      {dir === "ALL" ? "All" : dir}
                    </FilterChip>
                  ))}
                </div>
                <div className="flex flex-wrap gap-3">
                  <CompactSelect
                    id="signal-class"
                    label="Asset class"
                    value={filters.assetClass}
                    onChange={(value) => {
                      setUniversePage(1);
                      setFilters((f) => ({ ...f, assetClass: value }));
                    }}
                    options={MARKET_CLASS_FILTERS.map((cls) => ({
                      id: cls,
                      label: cls === "ALL" ? "All classes" : cls,
                    }))}
                  />
                  <CompactSelect
                    id="signal-status"
                    label="Status"
                    value={statusFilter}
                    onChange={(value) => setStatusFilter(value as StatusFilterId)}
                    options={STATUS_FILTERS.map((item) => ({
                      id: item.id,
                      label: item.label,
                    }))}
                  />
                  <CompactSelect
                    id="signal-sort"
                    label="Sort"
                    value={sort}
                    onChange={(value) => setSort(value as SignalSortKey)}
                    options={SORT_OPTIONS}
                  />
                  {sessions.length > 0 ? (
                    <CompactSelect
                      id="signal-session"
                      label="Session"
                      value={filters.session}
                      onChange={(value) => setFilters((f) => ({ ...f, session: value }))}
                      options={[
                        { id: "ALL", label: "All sessions" },
                        ...sessions.map((item) => ({ id: item, label: item })),
                      ]}
                    />
                  ) : null}
                  {regimes.length > 0 ? (
                    <CompactSelect
                      id="signal-regime"
                      label="Regime"
                      value={filters.regime}
                      onChange={(value) => setFilters((f) => ({ ...f, regime: value }))}
                      options={[
                        { id: "ALL", label: "All regimes" },
                        ...regimes.map((item) => ({ id: item, label: item })),
                      ]}
                    />
                  ) : null}
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
                  <ul
                    className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3"
                    aria-label="Signals"
                  >
                    {feedRows.map((row, i) => {
                      const dir = signalBoardDirection(row);
                      const symbol = str(row.broker_symbol || row.symbol, "—");
                      const freshness = signalFreshness(row);
                      return (
                        <li key={`${symbol}-${i}`}>
                          <button
                            type="button"
                            onClick={() => setSelected(row)}
                            className="h-full w-full rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-elevated)] p-4 text-left shadow-[var(--shadow-card)] transition duration-[var(--duration-os)] hover:border-[var(--accent)] hover:shadow-[var(--shadow-card-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div className="min-w-0">
                                <p className="truncate text-base font-semibold tracking-tight text-[var(--fg)]">
                                  {symbol}
                                </p>
                                <p className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                                  {presentField(row.asset_class)}
                                </p>
                              </div>
                              <div className="flex flex-col items-end gap-1">
                                <Badge tone={directionTone(dir)}>{dir}</Badge>
                                <Badge tone={freshnessTone(freshness)}>
                                  {signalFreshnessLabel(freshness)}
                                </Badge>
                              </div>
                            </div>
                            <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-sm sm:grid-cols-3">
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">
                                  Strength
                                </dt>
                                <dd className="tabular">{signalStrength(row)}</dd>
                              </div>
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">
                                  Confidence
                                </dt>
                                <dd className="tabular">
                                  {scoreDisplay(row.research_rank_score)}
                                </dd>
                              </div>
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">
                                  Price
                                </dt>
                                <dd className="tabular">
                                  {presentPrice(row.price ?? row.mid ?? row.bid)}
                                </dd>
                              </div>
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">
                                  Entry
                                </dt>
                                <dd className="tabular">
                                  {presentLevel(row.entry ?? row.entry_candidate, "Entry")}
                                </dd>
                              </div>
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">
                                  Stop loss
                                </dt>
                                <dd className="tabular">
                                  {presentLevel(row.stop_loss ?? row.SL_candidate, "SL")}
                                </dd>
                              </div>
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">
                                  Take profit
                                </dt>
                                <dd className="tabular">
                                  {presentLevel(row.take_profit ?? row.TP_candidate, "TP")}
                                </dd>
                              </div>
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">
                                  Risk/Reward
                                </dt>
                                <dd className="tabular">
                                  {scoreDisplay(row.RR ?? row.rr)}
                                </dd>
                              </div>
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">
                                  Regime
                                </dt>
                                <dd>{presentField(rowRegime(row))}</dd>
                              </div>
                              <div>
                                <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">
                                  Timestamp
                                </dt>
                                <dd className="text-xs text-[var(--fg-muted)]">
                                  {signalTimestampLabel(row)}
                                </dd>
                              </div>
                            </dl>
                            <p className="mt-3 line-clamp-2 text-[11px] text-[var(--fg-muted)]">
                              {signalWhyPreview(row)}
                            </p>
                            <p className="mt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--accent)]">
                              Why this signal
                            </p>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                  {feedLimit < sorted.length ? (
                    <div className="flex justify-center pt-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() =>
                          setFeedLimit((n) => n + SIGNAL_FEED_PAGE_SIZE)
                        }
                      >
                        Show more ({sorted.length - feedLimit} remaining)
                      </Button>
                    </div>
                  ) : null}
                </>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="min-w-0 space-y-4 pt-4">
          <div>
            <h2 className="text-sm font-medium text-[var(--fg)]">
              Research universe
            </h2>
            <p className="text-xs text-[var(--fg-subtle)]">
              Full broker-discovered catalogue — closed markets remain visible
            </p>
          </div>
          {universeQ.isLoading ? (
            <DeskSkeleton rows={6} />
          ) : filteredUniverse.length === 0 ? (
            <DeskEmpty
              icon={Radar}
              title="Universe unavailable"
              description="No instruments in the research catalogue for the current filters."
            />
          ) : (
            <>
              <div className="hidden min-w-0 overflow-x-auto md:block">
                <table
                  className="w-full min-w-[960px] text-left text-sm"
                  aria-label="Research universe"
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
                        Market
                      </th>
                      <th className="py-2 pr-3 font-medium" scope="col">
                        Signal
                      </th>
                      <th className="py-2 pr-3 font-medium" scope="col">
                        Price
                      </th>
                      <th className="py-2 pr-3 font-medium" scope="col">
                        Opportunity
                      </th>
                      <th className="py-2 pr-3 font-medium" scope="col">
                        Edge
                      </th>
                      <th className="py-2 pr-3 font-medium" scope="col">
                        RR
                      </th>
                      <th className="py-2 pr-3 font-medium" scope="col">
                        Freshness
                      </th>
                      <th className="py-2 pr-3 font-medium" scope="col">
                        Last analysis
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {universePageRows.map((row, i) => {
                      const symbol = str(
                        row.broker_symbol || row.canonical_symbol || row.symbol,
                        "—",
                      );
                      const market = marketStateBucket(row);
                      const lifecycle = researchLifecycleLabel(row);
                      const signalRow = signalRows.find(
                        (s) =>
                          str(s.broker_symbol || s.symbol, "").toUpperCase() ===
                          symbol.toUpperCase(),
                      );
                      const dir = signalRow
                        ? signalBoardDirection(signalRow)
                        : market === "CLOSED"
                          ? "MARKET CLOSED"
                          : "NO SIGNAL";
                      const freshness = signalFreshness(signalRow || row);
                      const dq =
                        row.data_quality && typeof row.data_quality === "object"
                          ? (row.data_quality as Record<string, unknown>)
                          : {};
                      const price =
                        row.bid ??
                        row.ask ??
                        dq.bid ??
                        dq.ask ??
                        signalRow?.price ??
                        signalRow?.mid;
                      return (
                        <tr
                          key={`${symbol}-uni-${i}`}
                          className="border-b border-[var(--border)]"
                        >
                          <td className="py-2 pr-3 font-medium">{symbol}</td>
                          <td className="py-2 pr-3">
                            {presentField(row.asset_class)}
                          </td>
                          <td className="py-2 pr-3">
                            <Badge
                              tone={
                                market === "OPEN"
                                  ? "success"
                                  : market === "CLOSED"
                                    ? "warning"
                                    : "neutral"
                              }
                            >
                              {market === "CLOSED" ? "MARKET CLOSED" : market}
                            </Badge>
                          </td>
                          <td className="py-2 pr-3">
                            <Badge
                              tone={
                                dir === "BUY" || dir === "SELL"
                                  ? directionTone(dir)
                                  : "neutral"
                              }
                            >
                              {dir}
                            </Badge>
                            <span className="ml-2 text-[10px] text-[var(--fg-subtle)]">
                              {lifecycle}
                            </span>
                          </td>
                          <td className="py-2 pr-3 tabular">
                            {market === "CLOSED" && price == null
                              ? "—"
                              : presentPrice(price)}
                          </td>
                          <td className="py-2 pr-3 tabular">
                            {scoreDisplay(
                              signalRow?.opportunity_score ??
                                (row.scorecard as Record<string, unknown> | undefined)
                                  ?.OPPORTUNITY_QUALITY,
                            )}
                          </td>
                          <td className="py-2 pr-3 tabular">
                            {scoreDisplay(
                              signalRow?.directional_edge ?? signalRow?.edge,
                            )}
                          </td>
                          <td className="py-2 pr-3 tabular">
                            {scoreDisplay(signalRow?.RR ?? signalRow?.rr)}
                          </td>
                          <td className="py-2 pr-3">
                            <Badge tone={freshnessTone(freshness)}>
                              {signalFreshnessLabel(freshness)}
                            </Badge>
                          </td>
                          <td className="py-2 pr-3 text-xs text-[var(--fg-muted)]">
                            {signalRow
                              ? signalTimestampLabel(signalRow)
                              : presentField(
                                  row.features_as_of ||
                                    row.last_quote_timestamp ||
                                    dq.last_quote_timestamp,
                                )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <ul className="grid gap-2 md:hidden" aria-label="Research universe">
                {universePageRows.map((row, i) => {
                  const symbol = str(
                    row.broker_symbol || row.canonical_symbol || row.symbol,
                    "—",
                  );
                  const market = marketStateBucket(row);
                  return (
                    <li
                      key={`${symbol}-uni-m-${i}`}
                      className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] p-3"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-semibold">{symbol}</p>
                          <p className="text-[11px] text-[var(--fg-subtle)]">
                            {presentField(row.asset_class)} · {researchLifecycleLabel(row)}
                          </p>
                        </div>
                        <Badge tone={market === "OPEN" ? "success" : "warning"}>
                          {market === "CLOSED" ? "MARKET CLOSED" : market}
                        </Badge>
                      </div>
                    </li>
                  );
                })}
              </ul>
              {universePageCount > 1 ? (
                <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                  <p className="text-xs text-[var(--fg-subtle)]">
                    {filteredUniverse.length} instruments · page {universePage} /{" "}
                    {universePageCount}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={universePage <= 1}
                      onClick={() => setUniversePage((p) => Math.max(1, p - 1))}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={universePage >= universePageCount}
                      onClick={() =>
                        setUniversePage((p) => Math.min(universePageCount, p + 1))
                      }
                    >
                      Next
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-[var(--fg-subtle)]">
                  {filteredUniverse.length} instruments
                </p>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Dialog open={selected != null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent aria-describedby={undefined}>
          {selected ? <IntelligenceDetail row={selected} kind="signal" /> : null}
        </SheetContent>
      </Dialog>
    </div>
  );
}
