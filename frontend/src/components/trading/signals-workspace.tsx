"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Radar, RefreshCw, SlidersHorizontal } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogTitle, SheetContent } from "@/components/ui/dialog";
import { DeskEmpty, DeskMetric, DeskSkeleton } from "@/components/desk/primitives";
import { FilterChip } from "@/components/trading/filter-chip";
import { IntelligenceDetail } from "@/components/trading/intelligence-detail";
import { SignalCard } from "@/components/trading/signal-card";
import { SignalsReferenceDesk } from "@/components/trading/signals-reference-desk";
import { signalCenterApi, tradingSessionApi } from "@/lib/api/endpoints";
import { asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";
import {
  ASSET_CLASS_ORDER,
  EMPTY_SIGNAL_FILTERS,
  filterSignalRows,
  normalizeAssetClass,
  normalizeSignalCenterPayload,
  researchSignalsEmptyCopy,
  resolveConnectionPresentation,
  SIGNAL_CENTER_QUERY_KEY,
  signalSummary,
  signalUpdatedAgo,
  sortSignalRows,
  TRADER_POLL_MS,
  type SignalFilterState,
  type SignalSortKey,
} from "@/lib/trading/trader-ux";
import { isGoldSymbol, MULTI_SYMBOL_ENABLED } from "@/lib/trading/gold-only";

const SORT_OPTIONS: Array<{ id: SignalSortKey; label: string }> = [
  { id: "strongest", label: "Strongest" },
  { id: "newest", label: "Newest" },
  { id: "instrument", label: "Symbol" },
  ...(MULTI_SYMBOL_ENABLED
    ? ([{ id: "asset_class" as const, label: "Asset class" }] as const)
    : []),
];

const MARKET_CLASS_FILTERS = MULTI_SYMBOL_ENABLED
  ? (["ALL", ...ASSET_CLASS_ORDER] as const)
  : (["METALS"] as const);

const STATUS_FILTERS = [
  { id: "ALL", label: "All" },
  { id: "ACTIVE", label: "Active" },
  { id: "RECENT", label: "Recent" },
] as const;

type StatusFilterId = (typeof STATUS_FILTERS)[number]["id"];

const SIGNAL_FEED_PAGE_SIZE = 40;

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
}: {
  filters: SignalFilterState;
  setFilters: (updater: SignalFilterState | ((prev: SignalFilterState) => SignalFilterState)) => void;
  statusFilter: StatusFilterId;
  setStatusFilter: (value: StatusFilterId) => void;
  sort: SignalSortKey;
  setSort: (value: SignalSortKey) => void;
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
          label="Instrument"
          value={MULTI_SYMBOL_ENABLED ? filters.assetClass : "METALS"}
          onChange={(value) => setFilters((f) => ({ ...f, assetClass: value }))}
          options={MARKET_CLASS_FILTERS.map((cls) => ({
            id: cls,
            label:
              cls === "ALL"
                ? "All assets"
                : cls === "METALS"
                  ? "XAUUSD (Gold)"
                  : cls.charAt(0) + cls.slice(1).toLowerCase(),
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

export function SignalsWorkspace() {
  const qc = useQueryClient();
  const [filters, setFilters] = useState<SignalFilterState>({
    ...EMPTY_SIGNAL_FILTERS,
    assetClass: MULTI_SYMBOL_ENABLED ? "ALL" : "METALS",
  });
  const [sort, setSort] = useState<SignalSortKey>("strongest");
  const [statusFilter, setStatusFilter] = useState<StatusFilterId>("ALL");
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [feedLimit, setFeedLimit] = useState(SIGNAL_FEED_PAGE_SIZE);
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

  const signalsQ = useQuery({
    queryKey: SIGNAL_CENTER_QUERY_KEY,
    queryFn: () => signalCenterApi.list({ enabled_only: false }),
    retry: false,
    refetchInterval: TRADER_POLL_MS,
    placeholderData: (prev) => prev,
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

  const signalRows = useMemo(() => {
    const rows = normalized.rows;
    if (MULTI_SYMBOL_ENABLED) {
      if (filters.assetClass !== "ALL") {
        return rows.filter(
          (row) => normalizeAssetClass(row.asset_class) === filters.assetClass,
        );
      }
      return rows;
    }
    return rows.filter((row) =>
      isGoldSymbol(String(row.broker_symbol || row.symbol || "")),
    );
  }, [filters.assetClass, normalized.rows]);

  const researchHealth = normalized.researchAnalysis ?? {};
  const workerStatus = String(researchHealth.status || "UNKNOWN").toUpperCase();
  const degradedReason =
    researchHealth.degraded_reason != null
      ? String(researchHealth.degraded_reason).trim()
      : "";
  const researchDegraded =
    workerStatus === "DEGRADED" ||
    workerStatus === "STOPPED" ||
    degradedReason.length > 0;

  const filtered = useMemo(() => {
    const next: SignalFilterState = { ...filters };
    if (statusFilter === "ACTIVE") next.freshness = "LIVE";
    else if (statusFilter === "RECENT") next.freshness = "RECENT";
    return filterSignalRows(signalRows, next);
  }, [filters, signalRows, statusFilter]);

  const sorted = useMemo(() => sortSignalRows(filtered, sort), [filtered, sort]);
  const feedRows = useMemo(() => sorted.slice(0, feedLimit), [feedLimit, sorted]);

  const emptyCopy = researchSignalsEmptyCopy({
    fetchError: Boolean(signalsQ.isError),
    fabricatedBlocked: normalized.fabricatedBlocked,
    empty: true,
    universeSize: normalized.universeSize,
    skipReasons: normalized.skipReasons,
    degradedReason:
      researchHealth.degraded_reason != null
        ? String(researchHealth.degraded_reason)
        : null,
    catalogueSource:
      researchHealth.catalogue_source != null
        ? String(researchHealth.catalogue_source)
        : null,
    researchStatus: workerStatus,
  });

  const summary = signalSummary({
    availability: signalsQ.isError ? "UNAVAILABLE" : availability,
    rows: signalRows,
    instrumentCount: normalized.universeSize ?? signalRows.length,
    lastUpdate: normalized.asOf,
  });

  const lastUpdateRel = normalized.asOf
    ? signalUpdatedAgo({ as_of: normalized.asOf, time_generated: normalized.asOf })
    : "Not available";

  async function refreshAnalysis() {
    setRefreshing(true);
    try {
      if (researchDegraded) {
        await signalCenterApi.refreshResearch();
      }
      await signalsQ.refetch();
      await qc.invalidateQueries({ queryKey: SIGNAL_CENTER_QUERY_KEY });
    } finally {
      setRefreshing(false);
    }
  }

  const researchBannerMessage =
    degradedReason ||
    (workerStatus === "STOPPED"
      ? "Research analysis is stopped — signals may be stale until a refresh completes."
      : workerStatus === "DEGRADED"
        ? "Research analysis is degraded — live scan may be incomplete."
        : "Research health reported an issue — retry to run one analysis cycle.");

  const researchFailed = Boolean(signalsQ.isError);

  return (
    <div className="min-w-0 space-y-5">
      <PageHeader
        title="Trading Signals"
        description="High-probability opportunities from live research. Figures reflect the API only—empty states stay empty when data is unavailable."
        actions={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <span className="hidden text-xs text-[var(--fg-subtle)] md:inline">
              Last updated: {lastUpdateRel}
            </span>
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
              Refresh analysis
            </Button>
          </div>
        }
      />

      <p className="text-xs text-[var(--fg-subtle)] md:hidden">Last updated: {lastUpdateRel}</p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <DeskMetric label="Markets" value={String(summary.markets)} />
        <DeskMetric label="Buy" value={String(summary.buy)} />
        <DeskMetric label="Sell" value={String(summary.sell)} />
        <DeskMetric label="Neutral" value={String(summary.neutral)} />
        <DeskMetric label="Active" value={String(summary.active)} />
        <DeskMetric label="Updated" value={lastUpdateRel} />
      </div>

      {researchDegraded ? (
        <div
          className="flex flex-col gap-3 rounded-[var(--radius-os)] border border-[var(--warning-border,var(--border))] bg-[var(--surface)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
          role="status"
        >
          <div className="min-w-0">
            <p className="text-sm font-medium text-[var(--fg)]">
              Research feed {workerStatus === "STOPPED" ? "stopped" : "degraded"}
            </p>
            <p className="mt-1 text-xs text-[var(--fg-muted)]">{researchBannerMessage}</p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            className="shrink-0"
            disabled={signalsQ.isFetching || refreshing}
            onClick={() => void refreshAnalysis()}
          >
            <RefreshCw
              className={cn(
                "h-3.5 w-3.5",
                (signalsQ.isFetching || refreshing) && "animate-spin",
              )}
            />
            Retry research refresh
          </Button>
        </div>
      ) : null}

      <div className="hidden md:block">
        <FilterControls
          filters={filters}
          setFilters={setFilters}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          sort={sort}
          setSort={setSort}
        />
      </div>

      {signalsQ.isLoading ? (
        <DeskSkeleton rows={8} />
      ) : researchFailed ? (
        <DeskEmpty
          icon={Radar}
          title={productEmptyTitle(emptyCopy.title)}
          description={`${emptyCopy.description} Retry when the research API is reachable.`}
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
          <SignalsReferenceDesk
            row={selected ?? sorted[0]}
            connected={
              connection.state === "CONNECTED" ||
              session.connection_status === "CONNECTED" ||
              session.connection_status === "RUNNING"
            }
          />
          <div className="flex items-center justify-between gap-3 pt-2">
            <h3 className="text-sm font-semibold text-[var(--fg)]">All signals</h3>
            <p className="text-xs text-[var(--fg-subtle)]">
              Select a card to focus the desk above
            </p>
          </div>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Signals">
            {feedRows.map((row, i) => {
              const symbol = str(row.broker_symbol || row.symbol, "N/A");
              const active =
                selected != null &&
                str(selected.broker_symbol || selected.symbol) === symbol;
              return (
                <li key={`${symbol}-${i}`}>
                  <div
                    className={cn(
                      active && "rounded-[var(--radius-os)] ring-2 ring-[var(--accent)]",
                    )}
                  >
                    <SignalCard row={row} onOpen={() => setSelected(row)} />
                  </div>
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
          />
        </SheetContent>
      </Dialog>

      <Dialog open={selected != null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent aria-describedby={undefined}>
          {selected ? <IntelligenceDetail row={selected} kind="signal" /> : null}
        </SheetContent>
      </Dialog>
    </div>
  );
}
