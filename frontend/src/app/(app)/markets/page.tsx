"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskSkeleton } from "@/components/desk/primitives";
import { ConnectionStatus } from "@/components/trading/connection-status";
import { MarketCatalogueRows, ResearchAdvisoryNote } from "@/components/trading/market-catalogue-rows";
import { marketUniverseApi, tradingSessionApi } from "@/lib/api/endpoints";
import { asList, asRecord } from "@/lib/desk";
import {
  catalogueViewState,
  isLiveBrokerCatalogue,
  mergeCatalogueRows,
  resolveConnectionPresentation,
} from "@/lib/trading/trader-ux";

export default function MarketsPage() {
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
    queryKey: ["market-universe-snapshot", "markets"],
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
  const rows =
    catalogue === "LIVE_ROWS"
      ? mergeCatalogueRows(
          instruments,
          asList(asRecord(universe.opportunity_board).rows).map(asRecord),
        )
      : [];

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        title="Markets"
        description="Instruments from your connected broker. Research cannot place orders."
        actions={
          <Button variant="secondary" asChild>
            <Link href="/research">Research</Link>
          </Button>
        }
      />
      <ConnectionStatus session={session} />
      <ResearchAdvisoryNote />
      <Card>
        <CardContent className="min-w-0 pt-4">
          {sessionQ.isLoading ? (
            <DeskSkeleton rows={4} />
          ) : noBroker ? (
            <DeskEmpty
              icon={Activity}
              title="BROKER NOT CONNECTED"
              description="Connect and verify your broker to load the live catalogue."
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
              title="CATALOGUE UNAVAILABLE"
              description="Broker market catalogue is currently unavailable. This is not an empty market."
              actionLabel="Connect Broker"
              actionHref="/broker"
            />
          ) : catalogue === "NOT_READY" || universeQ.isLoading ? (
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
        </CardContent>
      </Card>
    </div>
  );
}
