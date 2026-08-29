"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity, Radar } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { DeskEmpty, DeskSkeleton } from "@/components/desk/primitives";
import { ConnectionStatus } from "@/components/trading/connection-status";
import { marketUniverseApi, tradingSessionApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn, formatRelativeTime } from "@/lib/utils";
import {
  catalogueViewState,
  dataSourceLabel,
  defaultSortedSignals,
  EMPTY_SIGNAL_FILTERS,
  filterSignalRows,
  isHighConfidence,
  isLiveBrokerCatalogue,
  marketDataState,
  mergeCatalogueRows,
  mergeResearchSignalFields,
  presentAssetClasses,
  presentField,
  priceDisplay,
  resolveConnectionPresentation,
  rowRegime,
  rowSession,
  scoreDisplay,
  signalAvailability,
  signalBoardDirection,
  signalSummary,
  signalWhyFactors,
  SIGNALS_NOT_AUTHORIZATION,
  sortSignalRows,
  uniqueRowValues,
  unavailableSignalsTitle,
  type SignalFilterState,
  type SignalSortKey,
} from "@/lib/trading/trader-ux";

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
        "h-8 shrink-0 rounded-md border px-2.5 text-[11px] font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
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

function toneForDirection(dir: string): "success" | "warning" | "danger" | "neutral" {
  if (dir === "BUY") return "success";
  if (dir === "SELL") return "danger";
  return "neutral";
}

function toneForHealth(
  state: string,
): "success" | "warning" | "danger" | "neutral" {
  if (state === "LIVE") return "success";
  if (state === "STALE" || state === "MARKET_CLOSED" || state === "INSUFFICIENT_HISTORY") {
    return "warning";
  }
  if (state === "ERROR" || state === "NO_DATA" || state === "CATALOGUE_UNAVAILABLE") {
    return "danger";
  }
  return "neutral";
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3">
      <p className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">{label}</p>
      <p className="mt-1 truncate tabular text-lg font-semibold text-[var(--fg)]">{value}</p>
    </div>
  );
}

const SORT_OPTIONS: Array<{ id: SignalSortKey; label: string }> = [
  { id: "newest", label: "Newest" },
  { id: "confidence", label: "Confidence" },
  { id: "opportunity", label: "Opportunity" },
  { id: "edge", label: "Edge" },
  { id: "risk_reward", label: "Risk/Reward" },
  { id: "instrument", label: "Instrument" },
  { id: "asset_class", label: "Asset class" },
];

export function SignalsWorkspace() {
  const [filters, setFilters] = useState<SignalFilterState>(EMPTY_SIGNAL_FILTERS);
  const [sort, setSort] = useState<SignalSortKey | "backend">("backend");
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);

  const sessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    retry: false,
    refetchInterval: 15_000,
  });
  const session = asRecord(sessionQ.data);
  const connection = resolveConnectionPresentation(session);
  const liveCatalogue = isLiveBrokerCatalogue(session);
  const noBroker = connection.state === "BROKER_NOT_CONNECTED";
  const mismatch = connection.state === "ACCOUNT_SESSION_MISMATCH";

  const universeQ = useQuery({
    queryKey: ["market-universe-snapshot", "signals"],
    queryFn: () => marketUniverseApi.snapshot(),
    enabled: connection.connected && !mismatch && liveCatalogue && !sessionQ.isLoading,
    retry: false,
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
  const healths = useMemo(
    () => uniqueRowValues(rows, (row) => marketDataState(row)),
    [rows],
  );
  const ages = useMemo(
    () => uniqueRowValues(rows, (row) => {
      const ts = String(row.timestamp || row.features_as_of || "");
      return ts ? "HAS_AGE" : "";
    }),
    [rows],
  );

  const filtered = useMemo(() => filterSignalRows(rows, filters), [filters, rows]);
  const sorted = useMemo(
    () => (sort === "backend" ? defaultSortedSignals(filtered) : sortSignalRows(filtered, sort)),
    [filtered, sort],
  );

  const summary = signalSummary({
    availability,
    rows,
    instrumentCount: instruments.length,
    lastUpdate: universe.as_of,
  });
  const source = dataSourceLabel({
    liveBroker: liveCatalogue,
    catalogueSource: universe.catalogue_source ?? session.catalogue_source,
  });
  const unavailable = unavailableSignalsTitle({ noBroker, mismatch, catalogue });

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        title="Signals"
        description="Market intelligence for your connected broker. Not a trade authorization."
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

      <p className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-center text-[11px] font-medium uppercase tracking-wide text-[var(--fg-subtle)]">
        {SIGNALS_NOT_AUTHORIZATION}
      </p>

      <ConnectionStatus session={session} />

      <section aria-labelledby="signals-overview">
        <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="signals-overview" className="text-sm font-medium text-[var(--fg)]">
              Market intelligence
            </h2>
            <p className="text-xs text-[var(--fg-subtle)]">
              Live market state · Last updated {summary.lastUpdate} · Source {source}
            </p>
          </div>
          <Badge tone={availability === "LIVE_ROWS" || availability === "LIVE_EMPTY" ? "success" : "warning"}>
            {availability === "LIVE_ROWS" || availability === "LIVE_EMPTY" ? "LIVE DATA" : "NO DATA"}
          </Badge>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          <Metric label="Active signals" value={summary.active} />
          <Metric label="High-confidence" value={summary.highConfidence} />
          <Metric label="BUY candidates" value={summary.buy} />
          <Metric label="SELL candidates" value={summary.sell} />
          <Metric label="Watch" value={summary.watch} />
          <Metric label="Markets monitored" value={summary.markets} />
          <Metric label="Asset classes" value={summary.assetClasses} />
          <Metric label="Last update" value={summary.lastUpdate} />
        </div>
      </section>

      <Card>
        <CardContent className="min-w-0 space-y-4 pt-4">
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
              title="No ranked signals"
              description="The live broker catalogue was queried. No ranked research signals are available right now."
            />
          ) : (
            <>
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Direction">
                  {(["ALL", "BUY", "SELL", "WATCH"] as const).map((dir) => (
                    <Chip
                      key={dir}
                      active={filters.direction === dir}
                      onClick={() => setFilters((f) => ({ ...f, direction: dir }))}
                    >
                      {dir}
                    </Chip>
                  ))}
                </div>
                {classes.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5" role="group" aria-label="Asset class">
                    <Chip
                      active={filters.assetClass === "ALL"}
                      onClick={() => setFilters((f) => ({ ...f, assetClass: "ALL" }))}
                    >
                      All classes
                    </Chip>
                    {classes.map((cls) => (
                      <Chip
                        key={cls}
                        active={filters.assetClass === cls}
                        onClick={() => setFilters((f) => ({ ...f, assetClass: cls }))}
                      >
                        {cls}
                      </Chip>
                    ))}
                  </div>
                ) : null}
                {sessions.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5" role="group" aria-label="Session">
                    <Chip
                      active={filters.session === "ALL"}
                      onClick={() => setFilters((f) => ({ ...f, session: "ALL" }))}
                    >
                      All sessions
                    </Chip>
                    {sessions.map((item) => (
                      <Chip
                        key={item}
                        active={filters.session === item}
                        onClick={() => setFilters((f) => ({ ...f, session: item }))}
                      >
                        {item}
                      </Chip>
                    ))}
                  </div>
                ) : null}
                {regimes.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5" role="group" aria-label="Regime">
                    <Chip
                      active={filters.regime === "ALL"}
                      onClick={() => setFilters((f) => ({ ...f, regime: "ALL" }))}
                    >
                      All regimes
                    </Chip>
                    {regimes.map((item) => (
                      <Chip
                        key={item}
                        active={filters.regime === item}
                        onClick={() => setFilters((f) => ({ ...f, regime: item }))}
                      >
                        {item}
                      </Chip>
                    ))}
                  </div>
                ) : null}
                {confidences.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5" role="group" aria-label="Confidence">
                    <Chip
                      active={filters.confidence === "ALL"}
                      onClick={() => setFilters((f) => ({ ...f, confidence: "ALL" }))}
                    >
                      All confidence
                    </Chip>
                    {confidences.map((item) => (
                      <Chip
                        key={item}
                        active={filters.confidence === item}
                        onClick={() => setFilters((f) => ({ ...f, confidence: item }))}
                      >
                        {item}
                      </Chip>
                    ))}
                  </div>
                ) : null}
                {healths.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5" role="group" aria-label="Data health">
                    <Chip
                      active={filters.dataHealth === "ALL"}
                      onClick={() => setFilters((f) => ({ ...f, dataHealth: "ALL" }))}
                    >
                      All health
                    </Chip>
                    {healths.map((item) => (
                      <Chip
                        key={item}
                        active={filters.dataHealth === item}
                        onClick={() => setFilters((f) => ({ ...f, dataHealth: item }))}
                      >
                        {item}
                      </Chip>
                    ))}
                  </div>
                ) : null}
                {ages.includes("HAS_AGE") ? (
                  <div className="flex flex-wrap gap-1.5" role="group" aria-label="Signal age">
                    <Chip
                      active={filters.age === "ALL"}
                      onClick={() => setFilters((f) => ({ ...f, age: "ALL" }))}
                    >
                      All ages
                    </Chip>
                    <Chip
                      active={filters.age === "RECENT"}
                      onClick={() => setFilters((f) => ({ ...f, age: "RECENT" }))}
                    >
                      Recent
                    </Chip>
                    <Chip
                      active={filters.age === "STALE"}
                      onClick={() => setFilters((f) => ({ ...f, age: "STALE" }))}
                    >
                      Older
                    </Chip>
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
                    onChange={(e) => setSort(e.target.value as SignalSortKey | "backend")}
                  >
                    <option value="backend">Backend rank</option>
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
                <ul className="grid gap-3 lg:grid-cols-2" aria-label="Signals">
                  {sorted.map((row, i) => {
                    const dir = signalBoardDirection(row);
                    const symbol = str(row.broker_symbol || row.symbol, "—");
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
                              <Badge tone={toneForDirection(dir)}>{dir}</Badge>
                              <Badge tone={toneForHealth(str(row.data_state, "UNKNOWN"))}>
                                {str(row.data_state, "UNKNOWN")}
                              </Badge>
                              {isHighConfidence(row) ? (
                                <Badge tone="accent">Qualified</Badge>
                              ) : null}
                            </div>
                          </div>
                          <dl className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
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
                            <div>
                              <dt className="text-[10px] uppercase text-[var(--fg-subtle)]">Price</dt>
                              <dd className="tabular">
                                {priceDisplay(row.current_price ?? row.price ?? row.bid)}
                              </dd>
                            </div>
                          </dl>
                          <p className="mt-2 text-xs text-[var(--fg-muted)]">
                            {presentField(row.setup_state)} · {formatRelativeTime(str(row.timestamp || row.features_as_of, "")) || "Not available"}
                          </p>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Dialog open={selected != null} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="w-[min(96vw,720px)]" aria-describedby="signal-detail-note">
          {selected ? (
            <SignalDetail row={selected} />
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SignalDetail({ row }: { row: Record<string, unknown> }) {
  const dir = signalBoardDirection(row);
  const why = signalWhyFactors(row);
  return (
    <div className="space-y-4">
      <DialogTitle>
        {str(row.broker_symbol || row.symbol, "Signal")}
      </DialogTitle>
      <p id="signal-detail-note" className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
        {SIGNALS_NOT_AUTHORIZATION}
      </p>
      <div className="flex flex-wrap gap-1.5">
        <Badge tone={toneForDirection(dir)}>{dir}</Badge>
        <Badge tone={toneForHealth(str(row.data_state, "UNKNOWN"))}>
          {str(row.data_state, "UNKNOWN")}
        </Badge>
        <Badge tone="neutral">{presentField(row.asset_class)}</Badge>
        {isHighConfidence(row) ? <Badge tone="accent">Qualified</Badge> : null}
      </div>
      <dl className="grid gap-3 sm:grid-cols-2">
        <Detail label="Confidence" value={presentField(row.confidence_state)} />
        <Detail label="Opportunity" value={scoreDisplay(row.opportunity_score)} />
        <Detail label="Edge" value={scoreDisplay(row.directional_edge ?? row.edge)} />
        <Detail label="Risk/Reward" value={scoreDisplay(row.RR ?? row.rr)} />
        <Detail label="Market state" value={presentField(row.data_state)} />
        <Detail label="Regime" value={presentField(rowRegime(row))} />
        <Detail label="Session" value={presentField(rowSession(row))} />
        <Detail label="Current price" value={priceDisplay(row.current_price ?? row.price ?? row.bid)} />
        <Detail label="Entry context" value={presentField(row.entry_candidate)} />
        <Detail label="Stop-loss context" value={presentField(row.sl_candidate ?? row.SL_candidate)} />
        <Detail label="Take-profit context" value={presentField(row.tp_candidate ?? row.TP_candidate)} />
        <Detail label="Spread / data health" value={presentField(row.spread ?? row.data_freshness)} />
        <Detail label="Timestamp" value={presentField(row.timestamp || row.features_as_of)} />
        <Detail label="Status" value={presentField(row.board_status || row.setup_state)} />
      </dl>
      {why.length > 0 ? (
        <section>
          <h3 className="mb-2 text-sm font-medium text-[var(--fg)]">Why this signal</h3>
          <ul className="space-y-2">
            {why.map((factor) => (
              <li key={factor.label} className="rounded-md border border-[var(--border)] px-3 py-2">
                <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                  {factor.label}
                </p>
                <p className="text-sm text-[var(--fg)]">{factor.value}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <p className="text-sm text-[var(--fg-muted)]">Explanation not available.</p>
      )}
      <p className="text-xs text-[var(--fg-subtle)]">
        Signals are informational. There is no execute or place-order action on this desk.
      </p>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">{label}</dt>
      <dd className="text-sm text-[var(--fg)]">{value}</dd>
    </div>
  );
}
