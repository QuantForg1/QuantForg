"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskSkeleton } from "@/components/desk/primitives";
import { ConnectionStatus } from "@/components/trading/connection-status";
import { MarketCatalogueRows } from "@/components/trading/market-catalogue-rows";
import { marketUniverseApi, tradingSessionApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import {
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
  const universeLive =
    str(universe.catalogue_source) === "LIVE_BROKER" && instruments.length > 0;
  const rows = universeLive
    ? mergeCatalogueRows(
        instruments,
        asList(asRecord(universe.opportunity_board).rows).map(asRecord),
      )
    : [];

  const catalogueUnavailable =
    connection.catalogueUnavailable ||
    !liveCatalogue ||
    (universeQ.isFetched && !universeLive) ||
    universeQ.isError;

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        title="Markets"
        description="Broker-discovered catalogue for your connected account. Research cannot place orders."
        actions={
          <Button variant="secondary" asChild>
            <Link href="/research">Research</Link>
          </Button>
        }
      />
      <ConnectionStatus session={session} />
      <Card>
        <CardHeader>
          <CardTitle>Market catalogue</CardTitle>
        </CardHeader>
        <CardContent className="min-w-0 overflow-x-auto">
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
              title="ACCOUNT_SESSION_MISMATCH"
              description="This terminal is bound to another session. Reconnect your own account."
              actionLabel="Reconnect"
              actionHref="/broker"
            />
          ) : catalogueUnavailable ? (
            <DeskEmpty
              icon={Activity}
              title="CATALOGUE UNAVAILABLE"
              description="Connect or verify your broker and refresh market data. This is not an empty market."
              actionLabel="Connect Broker"
              actionHref="/broker"
            />
          ) : universeQ.isLoading ? (
            <DeskSkeleton rows={6} />
          ) : rows.length === 0 ? (
            <DeskEmpty
              icon={Activity}
              title="EMPTY"
              description="The live catalogue was queried. No instruments are listed for this session."
            />
          ) : (
            <MarketCatalogueRows rows={rows} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
