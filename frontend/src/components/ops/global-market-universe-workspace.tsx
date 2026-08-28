"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Globe2, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { marketUniverseApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const CLASSES = [
  "FOREX",
  "CRYPTO",
  "METALS",
  "INDICES",
  "ENERGY",
  "OTHER",
  "UNKNOWN",
] as const;

const TABS = [
  "Overview",
  "Opportunities",
  "Explorer",
  "Sessions",
  "Shadow",
  "Performance",
  "Quality",
  "Health",
] as const;

const DATA_STATES = [
  "ALL",
  "LIVE",
  "STALE",
  "NO_DATA",
  "MARKET_CLOSED",
  "INSUFFICIENT_HISTORY",
  "UNSUPPORTED",
  "ERROR",
  "UNKNOWN",
] as const;

const SESSIONS = [
  "ALL",
  "SYDNEY",
  "TOKYO",
  "LONDON",
  "LONDON_NY",
  "NEW_YORK",
] as const;

const REGIMES = [
  "ALL",
  "TREND",
  "RANGE",
  "BREAKOUT",
  "REVERSAL",
  "NEWS_VOLATILITY",
  "LOW_VOLATILITY",
  "UNKNOWN",
] as const;

function Panel({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
        {action}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function countOf(counts: Record<string, unknown>, key: string): string {
  const raw = counts[key];
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (trimmed !== "" && !Number.isFinite(Number(trimmed))) return trimmed;
  }
  const n = num(raw, NaN);
  return Number.isFinite(n) ? String(n) : "UNKNOWN";
}

function metric(label: string, value: unknown) {
  return (
    <div className="border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </div>
      <div className="mt-1 font-mono text-[13px] text-[var(--fg)]">
        {value == null || value === "" ? "UNKNOWN" : String(value)}
      </div>
    </div>
  );
}

function distRows(raw: unknown): Array<[string, string]> {
  const rec = asRecord(raw);
  return Object.entries(rec).map(([k, v]) => [k, String(v ?? "UNKNOWN")]);
}

function RankList({ rows, empty }: { rows: unknown[]; empty: string }) {
  if (rows.length === 0) {
    return <div className="font-mono text-[12px]">{empty}</div>;
  }
  return (
    <ul className="space-y-1 font-mono text-[12px]">
      {rows.slice(0, 20).map((row, i) => {
        const r = asRecord(row);
        return (
          <li key={`${str(r.canonical_symbol)}-${i}`}>
            {i + 1} RESEARCH SIGNAL {str(r.symbol)} {str(r.direction)}{" "}
            {str(r.opportunity_score)} {str(r.opportunity_tier, "")}{" "}
            {str(r.directional_edge)}
          </li>
        );
      })}
    </ul>
  );
}

export function GlobalMarketUniverseWorkspace() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const [assetFilter, setAssetFilter] = useState<string>("ALL");
  const [directionFilter, setDirectionFilter] = useState<string>("ALL");
  const [dataStateFilter, setDataStateFilter] = useState<string>("ALL");
  const [sessionFilter, setSessionFilter] = useState<string>("ALL");
  const [regimeFilter, setRegimeFilter] = useState<string>("ALL");
  const [minOpportunity, setMinOpportunity] = useState<string>("");
  const [minEdge, setMinEdge] = useState<string>("");
  const [selectedKey, setSelectedKey] = useState<string>("");
  const [explorerQuery, setExplorerQuery] = useState("");

  const snapQ = useQuery({
    queryKey: ["market-universe-snapshot"],
    queryFn: () => marketUniverseApi.snapshot(),
    staleTime: 15_000,
    refetchInterval: 60_000,
    retry: false,
  });
  const shadowQ = useQuery({
    queryKey: ["market-universe-shadow"],
    queryFn: () => marketUniverseApi.shadow(),
    enabled: tab === "Shadow",
    staleTime: 30_000,
    retry: false,
  });
  const perfQ = useQuery({
    queryKey: ["market-universe-performance"],
    queryFn: () => marketUniverseApi.performance(),
    enabled: tab === "Performance",
    staleTime: 30_000,
    retry: false,
  });

  const data = asRecord(snapQ.data);
  const counts = asRecord(data.global_market_status);
  const board = asRecord(data.opportunity_board);
  const shadow = asRecord(data.shadow);
  const sessionIntel = asRecord(data.session_intelligence);
  const regimeIntel = asRecord(data.regime_intelligence);
  const correlation = asRecord(data.correlation);
  const health = asRecord(data.broker_health);
  const scanner = asRecord(data.scanner_health);
  const layers = asRecord(data.layers);
  const instruments = useMemo(
    () => asList(data.instruments).map(asRecord),
    [data.instruments],
  );
  const rows = useMemo(
    () => asList(board.rows || board.top_opportunities).map(asRecord),
    [board.rows, board.top_opportunities],
  );
  const filtered = useMemo(() => {
    const oppFloor = minOpportunity.trim() === "" ? null : Number(minOpportunity);
    const edgeFloor = minEdge.trim() === "" ? null : Number(minEdge);
    return rows.filter((row) => {
      if (assetFilter !== "ALL" && str(row.asset_class).toUpperCase() !== assetFilter) {
        return false;
      }
      if (
        directionFilter !== "ALL" &&
        str(row.direction).toUpperCase() !== directionFilter
      ) {
        return false;
      }
      if (
        dataStateFilter !== "ALL" &&
        str(row.data_state).toUpperCase() !== dataStateFilter
      ) {
        return false;
      }
      if (
        sessionFilter !== "ALL" &&
        !str(row.session).toUpperCase().includes(sessionFilter)
      ) {
        return false;
      }
      if (regimeFilter !== "ALL") {
        const regime = str(asRecord(row.evidence).REGIME).toUpperCase();
        if (regime !== regimeFilter) return false;
      }
      if (oppFloor != null && Number.isFinite(oppFloor)) {
        const opp = num(row.opportunity_score, NaN);
        if (!Number.isFinite(opp) || opp < oppFloor) return false;
      }
      if (edgeFloor != null && Number.isFinite(edgeFloor)) {
        const edge = num(row.directional_edge, NaN);
        if (!Number.isFinite(edge) || edge < edgeFloor) return false;
      }
      return true;
    });
  }, [
    rows,
    assetFilter,
    directionFilter,
    dataStateFilter,
    sessionFilter,
    regimeFilter,
    minOpportunity,
    minEdge,
  ]);
  const selected = useMemo(() => {
    if (!selectedKey) return null;
    return (
      rows.find(
        (row) =>
          `${str(row.canonical_symbol)}:${str(row.broker_symbol)}` === selectedKey,
      ) ||
      instruments.find(
        (item) =>
          `${str(item.canonical_symbol)}:${str(item.broker_symbol)}` === selectedKey,
      ) ||
      null
    );
  }, [selectedKey, rows, instruments]);
  const explored = useMemo(() => {
    const q = explorerQuery.trim().toUpperCase();
    if (!q) return instruments.slice(0, 40);
    return instruments
      .filter((item) => {
        const hay = `${str(item.canonical_symbol)} ${str(item.broker_symbol)} ${str(item.asset_class)}`.toUpperCase();
        return hay.includes(q);
      })
      .slice(0, 40);
  }, [instruments, explorerQuery]);

  if (snapQ.isLoading && !snapQ.data) return <DeskSkeleton rows={8} />;
  if (snapQ.isError) {
    return (
      <DeskError message="Market universe unavailable. Live gold execution is unchanged." />
    );
  }

  const catalogueSource = str(data.catalogue_source, "UNAVAILABLE");
  const catalogueUnavailable = ["UNAVAILABLE", "ERROR", "MOCK"].includes(
    catalogueSource,
  );
  const emptyCatalogue =
    catalogueUnavailable || (Boolean(data.catalogue_empty) && rows.length === 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className="h-5" tone="neutral">
          RESEARCH
        </Badge>
        <Badge className="h-5" tone="neutral">
          NOT A TRADE AUTHORIZATION
        </Badge>
        <Badge className="h-5" tone="neutral">
          {catalogueSource}
        </Badge>
        <Badge className="h-5" tone="neutral">
          NEWS {str(data.NEWS_PROTECTION, "UNWIRED")}
        </Badge>
        <Badge className="h-5" tone="neutral">
          {catalogueSource === "LIVE_BROKER"
            ? "REAL BROKER CATALOGUE"
            : "CATALOGUE UNAVAILABLE"}
        </Badge>
        <span className="text-[12px] text-[var(--fg-muted)]">
          Live execution remains XAUUSD_i · Opportunity 70 · Edge 5
        </span>
        <Button
          size="sm"
          variant="outline"
          className="ml-auto"
          onClick={() => {
            void marketUniverseApi.refresh().then(() => snapQ.refetch());
          }}
        >
          Refresh snapshot
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {TABS.map((name) => (
          <Button
            key={name}
            size="sm"
            variant={tab === name ? "secondary" : "outline"}
            onClick={() => setTab(name)}
          >
            {name}
          </Button>
        ))}
      </div>

      {tab === "Overview" && (
        <>
          <Panel
            title="GLOBAL MARKET UNIVERSE"
            action={
              <span className="inline-flex items-center gap-1 text-[11px] text-[var(--fg-subtle)]">
                <Globe2 className="h-3.5 w-3.5" />
                ALL {countOf(counts, "universe")}
              </span>
            }
          >
            <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
              {metric("ALL", countOf(counts, "universe"))}
              {CLASSES.map((cls) => (
                <div key={cls}>{metric(cls, countOf(counts, cls))}</div>
              ))}
            </dl>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {metric("Data-ready", countOf(counts, "data_ready"))}
              {metric("Live", countOf(counts, "live"))}
              {metric("Stale", countOf(counts, "stale"))}
              {metric("Closed", countOf(counts, "market_closed"))}
              {metric("No data", countOf(counts, "no_data"))}
              {metric("Unsupported", countOf(counts, "unsupported"))}
              {metric("Error", countOf(counts, "error"))}
              {metric("Unknown class", countOf(counts, "UNKNOWN_CLASS"))}
              {metric("Shadow n", shadow.n ?? "INSUFFICIENT_SAMPLE")}
              {metric(
                "Research signals",
                asRecord(data.research_signals).n ?? "INSUFFICIENT_SAMPLE",
              )}
              {metric(
                "Research stage",
                str(asRecord(data.research_stage).stage, "DISCOVER"),
              )}
            </dl>
            <p className="mt-3 text-[11px] text-[var(--fg-muted)]">
              Opportunity is not profitability. RESEARCH_SIGNAL is not a LIVE_ORDER.
              {catalogueUnavailable
                ? ` reason = ${str(
                    data.reason ?? asRecord(data.connection).adapter_reason,
                    "broker_discovery_failed",
                  )}`
                : ""}
            </p>
          </Panel>
          <Panel title="Global opportunity · research only">
            <p className="mb-2 text-[11px] text-[var(--fg-muted)]">
              NOT A TRADE AUTHORIZATION · Best current research signal is not a
              guaranteed best trade
            </p>
            {str(asRecord(data.global_opportunity).status, "UNAVAILABLE") ===
              "UNAVAILABLE" ||
            str(asRecord(data.global_opportunity).status, "UNAVAILABLE") ===
              "MOCK" ? (
              <div className="font-mono text-[13px] text-[var(--fg)]">
                GLOBAL OPPORTUNITY ={" "}
                {str(asRecord(data.global_opportunity).value, "UNAVAILABLE")}
              </div>
            ) : (
              <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {metric(
                  "Status",
                  str(asRecord(data.global_opportunity).status, "INSUFFICIENT_SAMPLE"),
                )}
                {metric("Symbol", str(asRecord(data.global_opportunity).symbol, "UNKNOWN"))}
                {metric(
                  "Direction",
                  str(asRecord(data.global_opportunity).direction, "WAIT"),
                )}
                {metric(
                  "Opportunity",
                  asRecord(data.global_opportunity).value == null
                    ? "UNKNOWN"
                    : String(asRecord(data.global_opportunity).value),
                )}
              </dl>
            )}
          </Panel>
          <Panel title="Per asset class">
            <div className="grid gap-3 lg:grid-cols-3 xl:grid-cols-6">
              {CLASSES.map((cls) => {
                const classRows = rows.filter(
                  (r) => str(r.asset_class).toUpperCase() === cls,
                );
                const best = classRows[0];
                const buy = classRows.find(
                  (r) => str(r.direction).toUpperCase() === "BUY",
                );
                const sell = classRows.find(
                  (r) => str(r.direction).toUpperCase() === "SELL",
                );
                return (
                  <div
                    key={cls}
                    className="border border-[var(--border)] bg-[var(--surface-2)] p-3"
                  >
                    <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                      {cls}
                    </div>
                    <div className="mt-2 space-y-1 font-mono text-[12px] text-[var(--fg)]">
                      <div>Discovered {countOf(counts, cls)}</div>
                      <div>
                        Strongest{" "}
                        {catalogueUnavailable
                          ? "UNAVAILABLE"
                          : best
                            ? `${str(best.symbol)} ${str(best.opportunity_score)}`
                            : "INSUFFICIENT_SAMPLE"}
                      </div>
                      <div>
                        BUY{" "}
                        {catalogueUnavailable
                          ? "UNAVAILABLE"
                          : buy
                            ? str(buy.symbol)
                            : "INSUFFICIENT_SAMPLE"}
                      </div>
                      <div>
                        SELL{" "}
                        {catalogueUnavailable
                          ? "UNAVAILABLE"
                          : sell
                            ? str(sell.symbol)
                            : "INSUFFICIENT_SAMPLE"}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </Panel>
        </>
      )}

      {tab === "Opportunities" && (
        <>
          <Panel
            title="Global opportunity board"
            action={
              <span className="inline-flex items-center gap-1 text-[11px] text-[var(--fg-subtle)]">
                <Shield className="h-3.5 w-3.5" />
                Sort ≠ permission to trade
              </span>
            }
          >
            <div className="mb-3 flex flex-wrap gap-2">
              {["ALL", ...CLASSES].map((cls) => (
                <Button
                  key={cls}
                  size="sm"
                  variant={assetFilter === cls ? "secondary" : "outline"}
                  onClick={() => setAssetFilter(cls)}
                >
                  {cls}
                </Button>
              ))}
              {["ALL", "BUY", "SELL", "WAIT"].map((d) => (
                <Button
                  key={d}
                  size="sm"
                  variant={directionFilter === d ? "secondary" : "outline"}
                  onClick={() => setDirectionFilter(d)}
                >
                  {d}
                </Button>
              ))}
            </div>
            <div className="mb-3 flex flex-wrap gap-2">
              {DATA_STATES.map((state) => (
                <Button
                  key={state}
                  size="sm"
                  variant={dataStateFilter === state ? "secondary" : "outline"}
                  onClick={() => setDataStateFilter(state)}
                >
                  {state === "ALL" ? "DATA ALL" : state}
                </Button>
              ))}
            </div>
            <div className="mb-3 flex flex-wrap gap-2">
              {SESSIONS.map((sess) => (
                <Button
                  key={sess}
                  size="sm"
                  variant={sessionFilter === sess ? "secondary" : "outline"}
                  onClick={() => setSessionFilter(sess)}
                >
                  {sess === "ALL" ? "SESSION ALL" : sess}
                </Button>
              ))}
            </div>
            <div className="mb-3 flex flex-wrap gap-2">
              {REGIMES.map((reg) => (
                <Button
                  key={reg}
                  size="sm"
                  variant={regimeFilter === reg ? "secondary" : "outline"}
                  onClick={() => setRegimeFilter(reg)}
                >
                  {reg === "ALL" ? "REGIME ALL" : reg}
                </Button>
              ))}
            </div>
            <div className="mb-3 flex flex-wrap items-center gap-3 text-[11px] text-[var(--fg-subtle)]">
              <label className="flex items-center gap-2">
                Opportunity ≥
                <input
                  value={minOpportunity}
                  onChange={(event) => setMinOpportunity(event.target.value)}
                  inputMode="numeric"
                  placeholder="any"
                  className="w-16 border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1 font-mono text-[12px] text-[var(--fg)]"
                  aria-label="Minimum Opportunity"
                />
              </label>
              <label className="flex items-center gap-2">
                Edge ≥
                <input
                  value={minEdge}
                  onChange={(event) => setMinEdge(event.target.value)}
                  inputMode="numeric"
                  placeholder="any"
                  className="w-16 border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1 font-mono text-[12px] text-[var(--fg)]"
                  aria-label="Minimum directional edge"
                />
              </label>
              <span>RESEARCH ONLY · NOT A TRADE AUTHORIZATION</span>
            </div>
            {emptyCatalogue || catalogueUnavailable ? (
              <DeskEmpty
                icon={Globe2}
                title="CATALOGUE UNAVAILABLE"
                description={
                  catalogueUnavailable
                    ? "The live broker catalogue was not retrieved. This is not zero FOREX/CRYPTO/METALS. Fixtures are never shown as LIVE_BROKER. Live gold trading is unaffected."
                    : "The connected LIVE_BROKER catalogue contained no symbols."
                }
              />
            ) : filtered.length === 0 ? (
              <DeskEmpty
                icon={Globe2}
                title="No scored research rows"
                description="Board rows appear when LIVE_BROKER instruments have valid scores. Missing data is UNKNOWN, not Opportunity 0. RESEARCH ONLY · NOT A TRADE AUTHORIZATION."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[880px] text-left text-[12px]">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                    <tr>
                      <th className="py-2 pr-3">Rank</th>
                      <th className="py-2 pr-3">Symbol</th>
                      <th className="py-2 pr-3">Class</th>
                      <th className="py-2 pr-3">State</th>
                      <th className="py-2 pr-3">Dir</th>
                      <th className="py-2 pr-3">BUY</th>
                      <th className="py-2 pr-3">SELL</th>
                      <th className="py-2 pr-3">Opp</th>
                      <th className="py-2 pr-3">Tier</th>
                      <th className="py-2 pr-3">Edge</th>
                      <th className="py-2 pr-3">RR</th>
                      <th className="py-2 pr-3">Session</th>
                      <th className="py-2 pr-3">Regime</th>
                      <th className="py-2 pr-3">Freshness</th>
                      <th className="py-2">WAIT reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.slice(0, 40).map((row, i) => {
                      const key = `${str(row.canonical_symbol)}:${str(row.broker_symbol)}`;
                      return (
                      <tr
                        key={`${str(row.canonical_symbol)}-${i}`}
                        className={cn(
                          "cursor-pointer border-t border-[var(--border)] font-mono",
                          str(row.canonical_symbol) === "XAUUSD" &&
                            "text-[var(--accent)]",
                          selectedKey === key && "bg-[var(--surface-2)]",
                        )}
                        onClick={() => setSelectedKey(key)}
                      >
                        <td className="py-2 pr-3">{i + 1}</td>
                        <td className="py-2 pr-3">
                          RESEARCH SIGNAL {str(row.symbol)}
                        </td>
                        <td className="py-2 pr-3">{str(row.asset_class)}</td>
                        <td className="py-2 pr-3">{str(row.data_state, "UNKNOWN")}</td>
                        <td className="py-2 pr-3">{str(row.direction)}</td>
                        <td className="py-2 pr-3">{str(row.core_buy, "UNKNOWN")}</td>
                        <td className="py-2 pr-3">{str(row.core_sell, "UNKNOWN")}</td>
                        <td className="py-2 pr-3">
                          {row.opportunity_score == null
                            ? "UNKNOWN"
                            : String(row.opportunity_score)}
                        </td>
                        <td className="py-2 pr-3">
                          {str(row.opportunity_tier, "UNKNOWN")}
                        </td>
                        <td className="py-2 pr-3">
                          {row.directional_edge == null
                            ? "UNKNOWN"
                            : String(row.directional_edge)}
                        </td>
                        <td className="py-2 pr-3">{str(row.RR, "UNKNOWN")}</td>
                        <td className="py-2 pr-3">{str(row.session, "UNKNOWN")}</td>
                        <td className="py-2 pr-3">
                          {str(asRecord(row.evidence).REGIME, "UNKNOWN")}
                        </td>
                        <td className="py-2 pr-3">
                          {str(row.data_freshness, "UNKNOWN")}
                        </td>
                        <td className="py-2 text-[var(--fg-muted)]">
                          {str(row.direction).toUpperCase() === "WAIT"
                            ? str(row.blocker, "WAIT")
                            : str(row.board_status, "RESEARCH")}
                        </td>
                      </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
          {selected ? (
            <Panel title={`Instrument details · ${str(selected.symbol || selected.canonical_symbol)}`}>
              <p className="mb-2 text-[11px] text-[var(--fg-muted)]">
                RESEARCH ONLY · NOT A TRADE AUTHORIZATION · Opportunity is not profitability
              </p>
              <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {metric("Canonical", str(selected.canonical_symbol))}
                {metric("Broker", str(selected.broker_symbol))}
                {metric("Class", str(selected.asset_class))}
                {metric("Direction", str(selected.direction, "WAIT"))}
                {metric(
                  "Opportunity",
                  selected.opportunity_score == null
                    ? "UNKNOWN"
                    : String(selected.opportunity_score),
                )}
                {metric("Tier", str(selected.opportunity_tier, "UNKNOWN"))}
                {metric(
                  "Edge",
                  selected.directional_edge == null
                    ? "UNKNOWN"
                    : String(selected.directional_edge),
                )}
                {metric("Quality", str(selected.quality, "UNKNOWN"))}
                {metric("Spread", str(selected.spread, "UNKNOWN"))}
                {metric("Session", str(selected.session, "UNKNOWN"))}
                {metric(
                  "Regime",
                  str(asRecord(selected.evidence).REGIME, "UNKNOWN"),
                )}
                {metric("Data", str(selected.data_state, "UNKNOWN"))}
                {metric("Setup", str(selected.setup_state, "UNKNOWN"))}
                {metric("Capability", str(selected.capability_state, "DISCOVERED"))}
                {metric("Live execution", str(selected.live_execution_enabled, "false"))}
                {metric("Updated", str(selected.features_as_of || selected.timestamp, "UNKNOWN"))}
              </dl>
            </Panel>
          ) : null}
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Top BUY">
              <p className="mb-2 text-[11px] text-[var(--fg-muted)]">
                Research only. Not a trade authorization.
              </p>
              <RankList
                rows={asList(board.top_buy)}
                empty={
                  catalogueUnavailable ? "CATALOGUE UNAVAILABLE" : "INSUFFICIENT_SAMPLE"
                }
              />
            </Panel>
            <Panel title="Top SELL">
              <p className="mb-2 text-[11px] text-[var(--fg-muted)]">
                Research only. Not a trade authorization.
              </p>
              <RankList
                rows={asList(board.top_sell)}
                empty={
                  catalogueUnavailable ? "CATALOGUE UNAVAILABLE" : "INSUFFICIENT_SAMPLE"
                }
              />
            </Panel>
          </div>
        </>
      )}

      {tab === "Explorer" && (
        <Panel title="Symbol explorer">
          <input
            value={explorerQuery}
            onChange={(event) => setExplorerQuery(event.target.value)}
            placeholder="Filter canonical or broker symbol"
            className="mb-3 w-full border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 font-mono text-[12px] text-[var(--fg)]"
            aria-label="Filter symbols"
          />
          {explored.length === 0 ? (
            <DeskEmpty
              icon={Globe2}
              title={
                catalogueUnavailable
                  ? "CATALOGUE UNAVAILABLE"
                  : "No instruments in this snapshot"
              }
              description={
                catalogueUnavailable
                  ? "The live broker catalogue was not retrieved. This is not a zero-symbol book."
                  : "The explorer lists LIVE_BROKER symbols only."
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-[12px]">
                <thead className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  <tr>
                    <th className="py-2 pr-3">Canonical</th>
                    <th className="py-2 pr-3">Broker</th>
                    <th className="py-2 pr-3">Class</th>
                    <th className="py-2 pr-3">State</th>
                    <th className="py-2">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {explored.map((item, i) => (
                    <tr
                      key={`${str(item.canonical_symbol)}-${i}`}
                      className="border-t border-[var(--border)] font-mono"
                    >
                      <td className="py-2 pr-3">{str(item.canonical_symbol)}</td>
                      <td className="py-2 pr-3">{str(item.broker_symbol)}</td>
                      <td className="py-2 pr-3">{str(item.asset_class)}</td>
                      <td className="py-2 pr-3">
                        {str(asRecord(item.data_quality).state, "UNKNOWN")}
                      </td>
                      <td className="py-2">
                        {str(item.classification_source, "UNKNOWN")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}

      {tab === "Sessions" && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Panel title="Session map">
            <p className="mb-2 text-[11px] text-[var(--fg-muted)]">
              Research only. Session filters are not activated.
            </p>
            {distRows(sessionIntel.by_session).length === 0 ? (
              <div className="font-mono text-[12px]">INSUFFICIENT_SAMPLE</div>
            ) : (
              <ul className="space-y-1 font-mono text-[12px]">
                {distRows(sessionIntel.by_session).map(([k, v]) => (
                  <li key={k}>
                    {k}: {v}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel title="Regime map">
            <p className="mb-2 text-[11px] text-[var(--fg-muted)]">
              Research only. Regime filters are not activated.
            </p>
            {distRows(regimeIntel.by_regime).length === 0 ? (
              <div className="font-mono text-[12px]">INSUFFICIENT_SAMPLE</div>
            ) : (
              <ul className="space-y-1 font-mono text-[12px]">
                {distRows(regimeIntel.by_regime).map(([k, v]) => (
                  <li key={k}>
                    {k}: {v}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel title="Correlation map">
            <p className="mb-2 text-[11px] text-[var(--fg-muted)]">
              Does not bypass Risk. Live limits unchanged.
            </p>
            <div className="space-y-1 font-mono text-[12px]">
              <div>
                Flags{" "}
                {asList(correlation.flags).length
                  ? asList(correlation.flags).map(String).join(", ")
                  : "UNKNOWN"}
              </div>
              <div>Bypasses risk {String(correlation.bypasses_risk ?? false)}</div>
              <div>
                Direction {str(correlation.same_direction_concentration, "UNKNOWN")}
              </div>
              <div>
                Matrix{" "}
                {typeof correlation.correlation_matrix === "string"
                  ? str(correlation.correlation_matrix)
                  : "clusters"}
              </div>
            </div>
          </Panel>
        </div>
      )}

      {tab === "Shadow" && (
        <Panel title="Shadow lab">
          <p className="mb-2 text-[11px] text-[var(--fg-muted)]">
            RESEARCH SHADOW ONLY. Virtual entry requires known ENTRY+SL+TP at T.
            Same-bar rejected. SL wins if SL and TP share a future bar. Not OMS.
          </p>
          <div className="space-y-1 font-mono text-[12px]">
            <div>
              Virtual n{" "}
              {str(
                asRecord(data.shadow_virtual).n ?? asRecord(shadowQ.data).n ?? shadow.n,
                "INSUFFICIENT_SAMPLE",
              )}
            </div>
            <div>
              Completed{" "}
              {catalogueUnavailable
                ? "UNAVAILABLE"
                : str(asRecord(data.shadow_virtual).completed_n, "INSUFFICIENT_SAMPLE")}
            </div>
            <div>
              Candidate families{" "}
              {str(shadow.family_n ?? asRecord(shadowQ.data).n, "INSUFFICIENT_SAMPLE")}
            </div>
            <div>Ledger RESEARCH_SHADOW_ONLY</div>
            <div>would_submit_order false</div>
            <div>ALLOW_LIVE_PROMOTION false</div>
          </div>
        </Panel>
      )}

      {tab === "Performance" && (
        <Panel title="Research performance">
          <p className="mb-2 text-[11px] text-[var(--fg-muted)]">
            STRATEGY_MATCHED only. Win rate is never shown without n.
          </p>
          <div className="space-y-1 font-mono text-[12px]">
            <div>
              Matched{" "}
              {str(
                asRecord(perfQ.data).STRATEGY_MATCHED_SAMPLE,
                "INSUFFICIENT_SAMPLE",
              )}
            </div>
            <div>OOS {str(asRecord(asRecord(perfQ.data).oos).status, "INSUFFICIENT_SAMPLE")}</div>
            <div>
              Walk-forward{" "}
              {str(
                asRecord(asRecord(perfQ.data).walk_forward).status,
                "INSUFFICIENT_SAMPLE",
              )}
            </div>
          </div>
        </Panel>
      )}

      {tab === "Quality" && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Panel title="Opportunity distribution">
            {distRows(data.opportunity_distribution).length === 0 ? (
              <div className="font-mono text-[12px]">INSUFFICIENT_SAMPLE</div>
            ) : (
              <ul className="space-y-1 font-mono text-[12px]">
                {distRows(data.opportunity_distribution).map(([k, v]) => (
                  <li key={k}>
                    {k}: {v}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel title="Opportunity tiers">
            {distRows(data.opportunity_tier_distribution).length === 0 ? (
              <div className="font-mono text-[12px]">INSUFFICIENT_SAMPLE</div>
            ) : (
              <ul className="space-y-1 font-mono text-[12px]">
                {distRows(data.opportunity_tier_distribution).map(([k, v]) => (
                  <li key={k}>
                    {k}: {v}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel title="Promotion status">
            <p className="mb-2 text-[11px] text-[var(--fg-muted)]">
              LIVE_ELIGIBLE remains unreachable without human authorization.
            </p>
            {distRows(data.promotion_summary).length === 0 ? (
              <div className="font-mono text-[12px]">INSUFFICIENT_SAMPLE</div>
            ) : (
              <ul className="space-y-1 font-mono text-[12px]">
                {distRows(data.promotion_summary).map(([k, v]) => (
                  <li key={k}>
                    {k}: {v}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      )}

      {tab === "Health" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="Broker health">
            <div className="space-y-1 font-mono text-[12px]">
              <div>Adapter {str(health.mt5_adapter_found, "UNKNOWN")}</div>
              <div>Gateway {str(health.gateway_found, "UNKNOWN")}</div>
              <div>
                Connection {str(health.broker_connection_available, "UNKNOWN")}
              </div>
              <div>Discovery {str(health.symbol_discovery_function, "UNKNOWN")}</div>
              <div>Mock {str(health.is_mock, "UNKNOWN")}</div>
              <div>Token exposed {str(health.token_exposed, "false")}</div>
            </div>
          </Panel>
          <Panel title="Scanner health">
            <div className="space-y-1 font-mono text-[12px]">
              <div>Catalogue {catalogueSource}</div>
              <div>Batch {str(scanner.batch_size, "UNKNOWN")}</div>
              <div>Backoff s {str(scanner.retry_backoff_s, "UNKNOWN")}</div>
              <div>Isolated {str(scanner.isolated, "UNKNOWN")}</div>
              <div>Second engine {str(scanner.second_trading_engine, "false")}</div>
              <div>
                CORE {str(asRecord(layers.CORE).broker_symbol, "XAUUSD_i")}
              </div>
              <div>
                Expansion OMS {str(asRecord(layers.EXPANSION).may_reach_oms, "false")}
              </div>
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}
