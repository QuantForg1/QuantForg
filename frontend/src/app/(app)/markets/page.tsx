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
  catalogueViewState,
  dataSourceLabel,
  isLiveBrokerCatalogue,
  knownInstrumentCountLabel,
  lastUpdatedCopy,
  MARKET_UNIVERSE_QUERY_KEY,
  mergeCatalogueRows,
  resolveConnectionPresentation,
  skippedMalformedInstrumentCount,
  traderFacingErrorMessage,
  TRADER_POLL_MS,
  UNIVERSE_POLL_MS,
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
  const liveCatalogue = isLiveBrokerCatalogue(session);
  const noBroker = connection.state === "BROKER_NOT_CONNECTED";
  const mismatch = connection.state === "ACCOUNT_SESSION_MISMATCH";
  const canRefresh = connection.connected && !mismatch;

  const universeQ = useQuery({
    queryKey: MARKET_UNIVERSE_QUERY_KEY,
    queryFn: () => marketUniverseApi.snapshot(),
    enabled: connection.connected && !mismatch && liveCatalogue && !sessionQ.isLoading,
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
  const catalogue = catalogueViewState({
    connected: connection.connected,
    mismatch,
    liveBrokerSession: liveCatalogue,
    catalogueUnavailable: connection.catalogueUnavailable,
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
  const source = dataSourceLabel({
    liveBroker: liveCatalogue,
    catalogueSource: universe.catalogue_source ?? session.catalogue_source,
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
        description="BROKER-DISCOVERED MARKET UNIVERSE"
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
      {refreshError ? (
        <p className="text-sm text-[var(--warning)]" role="status">
          {refreshError}
        </p>
      ) : null}

      {sessionQ.isLoading ? (
        <DeskSkeleton rows={4} />
      ) : noBroker ? (
        <DeskEmpty
          icon={Activity}
          title="MARKETS UNAVAILABLE"
          description="BROKER NOT CONNECTED. Connect and verify your broker to load the live catalogue."
          actionLabel="Connect Broker"
          actionHref="/broker"
        />
      ) : mismatch ? (
        <DeskEmpty
          icon={Activity}
          title="ACCOUNT SESSION MISMATCH"
          description="This terminal is bound to another session. Reconnect your own account."
          actionLabel="Reconnect"
          actionHref="/broker"
        />
      ) : catalogue === "UNAVAILABLE" ? (
        <DeskEmpty
          icon={Activity}
          title="MARKETS UNAVAILABLE"
          description={
            str(session.catalogue_last_error, "").trim() ||
            "Broker market catalogue is currently unavailable. This is not an empty market."
          }
          actionLabel="Connect Broker"
          actionHref="/broker"
        />
      ) : catalogue === "NOT_READY" || universeQ.isLoading || refreshMut.isPending ? (
        <DeskSkeleton rows={6} />
      ) : catalogue === "LIVE_EMPTY" ? (
        <DeskEmpty
          icon={Activity}
          title="No markets in catalogue"
          description="The live broker catalogue was queried. No instruments are listed for your account."
        />
      ) : (
        <MarketCatalogueRows rows={rows} showFilters />
      )}
    </div>
  );
}
