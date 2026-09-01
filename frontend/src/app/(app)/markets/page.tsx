"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskSkeleton } from "@/components/desk/primitives";
import { ConnectionStatus } from "@/components/trading/connection-status";
import { MarketCatalogueRows, ResearchAdvisoryNote } from "@/components/trading/market-catalogue-rows";
import { marketUniverseApi, tradingSessionApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { ApiError } from "@/lib/api/client";
import {
  catalogueStatusLabel,
  dataSourceLabel,
  knownInstrumentCountLabel,
  lastUpdatedCopy,
  LIVE_BROKER,
  MARKET_UNIVERSE_QUERY_KEY,
  mergeCatalogueRows,
  resolveConnectionPresentation,
  skippedMalformedInstrumentCount,
  traderFacingErrorMessage,
  TRADER_POLL_MS,
  UNIVERSE_POLL_MS,
  researchUniverseViewState,
} from "@/lib/trading/trader-ux";

export default function MarketsPage() {
  const qc = useQueryClient();
  const sessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    retry: false,
    refetchInterval: TRADER_POLL_MS,
  });

  const session = asRecord(sessionQ.data);
  const connection = resolveConnectionPresentation(session);
  const noBroker = connection.state === "BROKER_NOT_CONNECTED";
  const mismatch = connection.state === "ACCOUNT_SESSION_MISMATCH";
  const canRefresh = true;

  const universeQ = useQuery({
    queryKey: MARKET_UNIVERSE_QUERY_KEY,
    queryFn: () => marketUniverseApi.snapshot(),
    retry: false,
    refetchInterval: UNIVERSE_POLL_MS,
  });

  const refreshMut = useMutation({
    mutationFn: () => marketUniverseApi.refresh(),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["trading-session"] });
      await qc.invalidateQueries({ queryKey: MARKET_UNIVERSE_QUERY_KEY });
    },
  });

  const universe = asRecord(universeQ.data);
  const instruments = asList(universe.instruments).map(asRecord);
  const skipped = skippedMalformedInstrumentCount(instruments);
  const catalogue = researchUniverseViewState({
    snapshotFetched: universeQ.isFetched,
    snapshotError: Boolean(universeQ.isError),
    catalogueSource: universe.catalogue_source,
    instrumentCount: instruments.length - skipped,
  });
  const rows =
    catalogue === "LIVE_ROWS"
      ? mergeCatalogueRows(
          instruments,
          asList(asRecord(universe.opportunity_board).rows).map(asRecord),
        )
      : [];
  const globalSource = String(universe.catalogue_source || "").trim().toUpperCase();
  const source = dataSourceLabel({
    liveBroker: globalSource === LIVE_BROKER,
    catalogueSource: universe.catalogue_source,
  });
  const status = catalogueStatusLabel(catalogue);
  const instrumentCount = knownInstrumentCountLabel(catalogue, rows.length);
  const updated = lastUpdatedCopy(universe.as_of);
  const refreshError =
    refreshMut.isError
      ? refreshMut.error instanceof ApiError
        ? traderFacingErrorMessage(refreshMut.error)
        : "CATALOGUE_UNAVAILABLE"
      : null;

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        title="Markets"
        description="Global research universe — broker-discovered catalogue. Personal MT5 is not required."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={!canRefresh || refreshMut.isPending}
              onClick={() => refreshMut.mutate()}
            >
              {refreshMut.isPending ? "Refreshing…" : "Refresh catalogue"}
            </Button>
            <Button variant="secondary" size="sm" asChild>
              <Link href="/signals">Signals</Link>
            </Button>
          </div>
        }
      />

      <section
        aria-label="Markets command"
        className="flex flex-wrap items-center gap-2"
      >
        <ConnectionStatus session={session} compact />
        <Badge
          tone={
            catalogue === "LIVE_ROWS"
              ? "success"
              : catalogue === "LIVE_EMPTY"
                ? "neutral"
                : "warning"
          }
        >
          {status}
        </Badge>
        <Badge
          tone={source === "LIVE_BROKER" ? "success" : "warning"}
        >
          {source}
        </Badge>
        {instrumentCount ? (
          <span className="text-xs text-[var(--fg-subtle)]">
            {instrumentCount} instrument{instrumentCount === "1" ? "" : "s"}
          </span>
        ) : null}
        {updated ? (
          <span className="text-xs text-[var(--fg-subtle)]">{updated}</span>
        ) : null}
        {skipped > 0 && catalogue === "LIVE_ROWS" ? (
          <span className="text-xs text-[var(--fg-subtle)]">
            {skipped} invalid row{skipped === 1 ? "" : "s"} skipped
          </span>
        ) : null}
      </section>
      <ResearchAdvisoryNote />
      {noBroker ? (
        <p className="text-sm text-[var(--fg-muted)]" role="status">
          GLOBAL RESEARCH AVAILABLE. Personal broker: not connected.
          Live trading unavailable until broker connection.
        </p>
      ) : null}
      {mismatch ? (
        <p className="text-sm text-[var(--warning)]" role="status">
          ACCOUNT SESSION MISMATCH — live trading is blocked. Global research remains available.
        </p>
      ) : null}
      {refreshError ? (
        <p className="text-sm text-[var(--warning)]" role="status">
          {refreshError}
        </p>
      ) : null}

      {catalogue === "NOT_READY" || universeQ.isLoading || refreshMut.isPending ? (
        <DeskSkeleton rows={6} />
      ) : catalogue === "UNAVAILABLE" ? (
        <DeskEmpty
          icon={Activity}
          title="RESEARCH CATALOGUE UNAVAILABLE"
          description={
            str(universe.reason || session.catalogue_last_error, "").trim() ||
            "Global market catalogue is currently unavailable. This is not an empty market."
          }
        />
      ) : catalogue === "LIVE_EMPTY" ? (
        <DeskEmpty
          icon={Activity}
          title="No markets in catalogue"
          description="The live broker catalogue was queried. No instruments are listed."
        />
      ) : (
        <MarketCatalogueRows rows={rows} showFilters />
      )}
    </div>
  );
}
