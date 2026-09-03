"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Radar, RefreshCw, SlidersHorizontal } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogTitle, SheetContent } from "@/components/ui/dialog";
import { DeskEmpty, DeskMetric, DeskSkeleton } from "@/components/desk/primitives";
import { FilterChip } from "@/components/trading/filter-chip";
import { IntelligenceDetail } from "@/components/trading/intelligence-detail";
import { DirectionBadge, SignalCard } from "@/components/trading/signal-card";
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
  MARKET_PAGE_SIZE,
  MARKET_UNIVERSE_QUERY_KEY,
  marketStateBucket,
  normalizeAssetClass,
  normalizeSignalCenterPayload,
  presentField,
  presentPrice,
  presentUnavailable,
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
  signalBoardDirection,
  signalFreshness,
  signalFreshnessLabel,
  signalSummary,
  signalTimestampLabel,
  signalUpdatedAgo,
  sortSignalRows,
  TRADER_POLL_MS,
  UNIVERSE_POLL_MS,
  uniqueRowValues,
  type AnalysisDeskStatus,
  type SignalFilterState,
  type SignalSortKey,
} from "@/lib/trading/trader-ux";
import { freshnessTone } from "@/components/trading/intelligence-detail";

const SORT_OPTIONS: Array<{ id: SignalSortKey; label: string }> = [
  { id: "strongest", label: "Strongest" },
  { id: "newest", label: "Newest" },
  { id: "instrument", label: "Symbol" },
  { id: "asset_class", label: "Asset class" },
];

const MARKET_CLASS_FILTERS = ["ALL", ...ASSET_CLASS_ORDER] as const;
const SIGNAL_FEED_PAGE_SIZE = 40;
const STATUS_FILTERS = [
  { id: "ALL", label: "All" },
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

function FilterControls({
  filters,
  setFilters,
  statusFilter,
  setStatusFilter,
  sort,
  setSort,
  setUniversePage,
}: {
  filters: SignalFilterState;
  setFilters: (updater: SignalFilterState | ((prev: SignalFilterState) => SignalFilterState)) => void;
  statusFilter: StatusFilterId;
  setStatusFilter: (value: StatusFilterId) => void;
  sort: SignalSortKey;
  setSort: (value: SignalSortKey) => void;
  setUniversePage: (value: number | ((n: number) => number)) => void;
}) {
  return (
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
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <CompactSelect
          id="signal-class"
          label="Asset"
          value={filters.assetClass}
          onChange={(value) => {
            setUniversePage(1);
            setFilters((f) => ({ ...f, assetClass: value }));
          }}
          options={MARKET_CLASS_FILTERS.map((cls) => ({
            id: cls,
            label: cls === "ALL" ? "All" : cls.charAt(0) + cls.slice(1).toLowerCase(),
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
      </div>
    </div>
  );
}

function productEmptyTitle(title: string): string {
  if (title === "DATA UNAVAILABLE") return "Signals unavailable";
  if (title === "NO ACTIVE SIGNALS") return "No signals";
  return title;
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

function researchStatusLabel(input: {
  fetchError: boolean;
  workerStatus: string;
  loading: boolean;
}): string {
  if (input.fetchError) return "UNAVAILABLE";
  if (input.loading) return "RUNNING";
  if (input.workerStatus === "STOPPED") return "STOPPED";
  if (input.workerStatus === "DEGRADED") return "DEGRADED";
  if (input.workerStatus === "UNAVAILABLE") return "UNAVAILABLE";
  return "RUNNING";
}

function priceCell(value: unknown): string {
  const shown = presentPrice(value);
  return shown === "Price unavailable" ? "N/A" : presentUnavailable(shown);
}

function StatusDot({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <span className="inline-flex items-baseline gap-1.5 text-sm">
      <span className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
        {label}
      </span>
      <span className="font-medium text-[var(--fg)]">{value}</span>
    </span>
  );
}

export function SignalsWorkspace() {
  const qc = useQueryClient();
  const [filters, setFilters] = useState<SignalFilterState>(EMPTY_SIGNAL_FILTERS);
  const [sort, setSort] = useState<SignalSortKey>("strongest");
  const [statusFilter, setStatusFilter] = useState<StatusFilterId>("ACTIVE");
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [feedLimit, setFeedLimit] = useState(SIGNAL_FEED_PAGE_SIZE);
  const [universePage, setUniversePage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const sessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    retry: false,
    refetchInterval: TRADER_POLL_MS,
    staleTime: 10_000,
    placeholderData: (prev) => prev,
  });
  const session = asRecord(sessionQ.data);
  const connection = resolveConnectionPresentation(session);
  const accountHint = accountConnectionHint(connection);

  const signalsQ = useQuery({
    queryKey: SIGNAL_CENTER_QUERY_KEY,
    queryFn: () => signalCenterApi.list({ enabled_only: false }),
    retry: false,
    refetchInterval: TRADER_POLL_MS,
    placeholderData: (prev) => prev,
  });

  const universeQ = useQuery({
    queryKey: MARKET_UNIVERSE_QUERY_KEY,
    queryFn: () => marketUniverseApi.snapshot(),
    retry: false,
    refetchInterval: UNIVERSE_POLL_MS,
    placeholderData: (prev) => prev,
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
  const signalRows = normalized.rows;
  const researchHealth = normalized.researchAnalysis ?? {};
  const workerStatus = String(researchHealth.status || "UNKNOWN").toUpperCase();
  const researchLabel = researchStatusLabel({
    fetchError: Boolean(signalsQ.isError),
    workerStatus,
    loading: signalsQ.isLoading,
  });

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
  const liveTradingHint = researchDeskLiveTradingStatus(connection, session.trading, {
    liveTradingState: session.live_trading_state || normalized.liveTradingState,
    ordersMaySubmit:
      session.orders_may_submit === true || normalized.ordersMaySubmit === true,
    liveAuthorization: session.live_authorization || normalized.liveAuthorization,
  });
  const emptyCopy = researchSignalsEmptyCopy({
    fetchError: Boolean(signalsQ.isError),
    fabricatedBlocked: normalized.fabricatedBlocked,
    empty: true,
    universeSize: normalized.universeSize,
  });
  const coverageLabel = researchCoverageLabel(researchHealth);
  const progressCopy = researchProgressCopy(researchHealth);
  const discoveredLabel =
    researchHealth.instruments_discovered != null
      ? String(researchHealth.instruments_discovered)
      : "N/A";
  const eligibleLabel =
    researchHealth.instruments_eligible != null
      ? String(researchHealth.instruments_eligible)
      : "N/A";
  const analyzedLabel =
    researchHealth.instruments_analyzed != null
      ? String(researchHealth.instruments_analyzed)
      : "N/A";
  const failedLabel =
    researchHealth.instruments_failed != null
      ? String(researchHealth.instruments_failed)
      : "N/A";
  const unavailableLabel =
    researchHealth.instruments_unavailable != null
      ? String(researchHealth.instruments_unavailable)
      : "N/A";
  const coverageState = String(researchHealth.coverage_state || "").toUpperCase();
  const lifecycle = researchLifecycleCounts(universeInstruments);
  const assetClassCounts =
    researchHealth.asset_class_counts &&
    typeof researchHealth.asset_class_counts === "object"
      ? (researchHealth.asset_class_counts as Record<string, unknown>)
      : {};

  const summary = signalSummary({
    availability: signalsQ.isError ? "UNAVAILABLE" : availability,
    rows: signalRows,
    instrumentCount: normalized.universeSize ?? universeInstruments.length,
    lastUpdate: normalized.asOf,
  });
  const lastUpdateRel = normalized.asOf
    ? signalUpdatedAgo({ as_of: normalized.asOf, time_generated: normalized.asOf })
    : "Not available";

  async function refreshAnalysis() {
    setRefreshing(true);
    try {
      await marketUniverseApi.refresh().catch(() => null);
      await qc.invalidateQueries({ queryKey: MARKET_UNIVERSE_QUERY_KEY });
      await signalsQ.refetch();
    } finally {
      setRefreshing(false);
    }
  }

  const brokerLabel =
    accountHint.detail === "CONNECTED"
      ? "CONNECTED"
      : accountHint.detail === "SESSION MISMATCH"
        ? "SESSION MISMATCH"
        : "NOT CONNECTED";

  const researchFailed = Boolean(signalsQ.isError);

  return (
    <div className="min-w-0 space-y-5">
      <PageHeader
        eyebrow="Signals"
        title="GLOBAL MARKET SIGNALS"
        description="Research opportunities ranked by strength. Live execution still requires the existing risk, OMS, and broker gates."
        actions={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <div className="hidden min-w-[12rem] md:block">
              <Input
                value={filters.q}
                onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
                placeholder="Search"
                aria-label="Search signals"
              />
            </div>
            <Button
              variant="secondary"
              size="sm"
              className="md:hidden"
              onClick={() => setFiltersOpen(true)}
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              Filters
            </Button>
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
              Refresh
            </Button>
          </div>
        }
      />

      <p className="text-sm text-[var(--fg-muted)]">
        Research does not require a personal MT5 session. Live trading is a separate
        authorized step.
      </p>

      <section
        aria-label="Research, broker, and live trading"
        className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-4 py-2.5"
      >
        <StatusDot label="Research" value={researchLabel} />
        <StatusDot label="Broker" value={brokerLabel} />
        <StatusDot
          label="MT5"
          value={
            session.connection_status === "CONNECTED" ||
            session.connection_status === "RUNNING"
              ? "ATTACHED"
              : "DETACHED"
          }
        />
        <StatusDot label="Live trading" value={liveTradingHint.label} />
        <StatusDot
          label="Execution"
          value={
            session.orders_may_submit === true || normalized.ordersMaySubmit === true
              ? "READY"
              : "BLOCKED"
          }
        />
        <StatusDot
          label="Robot"
          value={str(session.robot, "UNKNOWN").toUpperCase()}
        />
      </section>

      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-[var(--fg-muted)]">
        <span>{summary.markets} Markets</span>
        <span>{analyzedLabel === "N/A" ? summary.markets : analyzedLabel} Analyzed</span>
        <span className="text-[var(--success)]">{summary.buy} BUY</span>
        <span className="text-[var(--danger)]">{summary.sell} SELL</span>
        <span>{summary.neutral} NEUTRAL</span>
        <span className="text-[var(--fg-subtle)]">Last update: {lastUpdateRel}</span>
      </p>

      <div className="hidden md:block">
        <FilterControls
          filters={filters}
          setFilters={setFilters}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          sort={sort}
          setSort={setSort}
          setUniversePage={setUniversePage}
        />
      </div>

      {signalsQ.isLoading ? (
        <DeskSkeleton rows={8} />
      ) : researchFailed ? (
        <DeskEmpty
          icon={Radar}
          title={productEmptyTitle(emptyCopy.title)}
          description={`${emptyCopy.description} Research is independent of your broker connection. Retry when the research API is reachable.`}
        />
      ) : availability === "NOT_READY" ? (
        <DeskSkeleton rows={8} />
      ) : availability === "LIVE_EMPTY" || signalRows.length === 0 ? (
        <DeskEmpty
          icon={Activity}
          title={productEmptyTitle(emptyCopy.title)}
          description={emptyCopy.description}
        />
      ) : sorted.length === 0 ? (
        <DeskEmpty
          icon={Activity}
          title="No matching signals"
          description="No signals match the current filters."
        />
      ) : (
        <>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Signals">
            {feedRows.map((row, i) => {
              const symbol = str(row.broker_symbol || row.symbol, "N/A");
              return (
                <li key={`${symbol}-${i}`}>
                  <SignalCard row={row} onOpen={() => setSelected(row)} />
                </li>
              );
            })}
          </ul>
        </>
      )}

      {sorted.length > 0 && feedLimit < sorted.length ? (
        <div className="flex justify-center">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setFeedLimit((n) => n + SIGNAL_FEED_PAGE_SIZE)}
          >
            Show more ({sorted.length - feedLimit} remaining)
          </Button>
        </div>
      ) : null}

      <details className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
        <summary className="cursor-pointer rounded-sm text-sm font-medium text-[var(--fg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
          Coverage
        </summary>
        <p className="mt-2 text-xs leading-relaxed text-[var(--fg-subtle)]">
          Eligible coverage is the subset research can analyze. Catalogue coverage is every
          discovered instrument, including closed and unavailable markets. QuantForg never
          claims 100% global coverage.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
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
                  className="rounded-md bg-[var(--surface-2)] px-2 py-1 text-[11px] text-[var(--fg-muted)]"
                >
                  {cls} · {String(raw)}
                </span>
              );
            })}
          </div>
        ) : null}
      </details>

      <details className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
        <summary className="cursor-pointer rounded-sm text-sm font-medium text-[var(--fg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
          Advanced
        </summary>
        <div className="mt-3 space-y-3">
          <p className="text-xs text-[var(--fg-subtle)]">
            {progressCopy || "Research analysis does not require a personal broker connection."}
          </p>
          <div className="flex flex-wrap gap-2">
            <Badge tone={analysisTone(analysisStatus)}>{analysisLabel}</Badge>
            <Badge tone={researchWorkerTone(workerStatus)}>
              Engine {workerStatus === "UNKNOWN" ? "—" : workerStatus}
            </Badge>
            {coverageState && coverageState !== "UNKNOWN" ? (
              <Badge tone={coverageState === "READY" ? "success" : "warning"}>
                {coverageState}
              </Badge>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-3">
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
      </details>

      <Dialog open={filtersOpen} onOpenChange={setFiltersOpen}>
        <SheetContent aria-describedby={undefined}>
          <DialogTitle>Filters</DialogTitle>
          <p className="mt-1 mb-4 text-sm text-[var(--fg-muted)]">
            Search, direction, asset class, status, and sort.
          </p>
          <FilterControls
            filters={filters}
            setFilters={setFilters}
            statusFilter={statusFilter}
            setStatusFilter={setStatusFilter}
            sort={sort}
            setSort={setSort}
            setUniversePage={setUniversePage}
          />
        </SheetContent>
      </Dialog>

      <details className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
        <summary className="cursor-pointer rounded-sm text-sm font-medium text-[var(--fg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
          Catalogue coverage
        </summary>
        <p className="mt-2 mb-3 text-xs leading-relaxed text-[var(--fg-subtle)]">
          Full discovered catalogue — closed and unavailable instruments stay visible and were
          not necessarily analyzed.
        </p>
        <div className="min-w-0 space-y-4">
          {universeQ.isLoading && universeInstruments.length === 0 ? (
            <DeskSkeleton rows={6} />
          ) : universeQ.isError && universeInstruments.length === 0 ? (
            <DeskEmpty
              icon={Radar}
              title="Catalogue timed out"
              description="Signals above remain from the research API. Catalogue snapshot is independent and will retry."
            />
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
                        "N/A",
                      );
                      const market = marketStateBucket(row);
                      const lifecycleLabel = researchLifecycleLabel(row);
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
                            {presentUnavailable(presentField(row.asset_class))}
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
                            <DirectionBadge dir={dir} />
                            <span className="ml-2 text-[10px] text-[var(--fg-subtle)]">
                              {lifecycleLabel}
                            </span>
                          </td>
                          <td className="py-2 pr-3 tabular">{priceCell(price)}</td>
                          <td className="py-2 pr-3 tabular">
                            {presentUnavailable(
                              scoreDisplay(
                                signalRow?.opportunity_score ??
                                  (row.scorecard as Record<string, unknown> | undefined)
                                    ?.OPPORTUNITY_QUALITY,
                              ),
                            )}
                          </td>
                          <td className="py-2 pr-3">
                            <Badge tone={freshnessTone(freshness)}>
                              {signalFreshnessLabel(freshness)}
                            </Badge>
                          </td>
                          <td className="py-2 pr-3 text-xs text-[var(--fg-muted)]">
                            {signalRow
                              ? signalTimestampLabel(signalRow)
                              : presentUnavailable(
                                  presentField(
                                    row.features_as_of ||
                                      row.last_quote_timestamp ||
                                      dq.last_quote_timestamp,
                                  ),
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
                    "N/A",
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
        </div>
      </details>

      <Dialog open={selected != null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent aria-describedby={undefined}>
          {selected ? <IntelligenceDetail row={selected} kind="signal" /> : null}
        </SheetContent>
      </Dialog>
    </div>
  );
}
