"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskSkeleton } from "@/components/desk/primitives";
import { marketUniverseApi, tradingSessionApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import {
  RESEARCH_NOT_AUTHORIZATION,
  instrumentName,
  isLiveBrokerCatalogue,
  MARKET_UNIVERSE_QUERY_KEY,
  marketDataState,
  mergeCatalogueRows,
  numericDisplay,
  priceDisplay,
  resolveConnectionPresentation,
  rowDirection,
  rowRegime,
  rowSession,
  scoreDisplay,
  signalFreshness,
  TRADER_POLL_MS,
  UNIVERSE_POLL_MS,
} from "@/lib/trading/trader-ux";

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3">
      <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">{label}</p>
      <p className="mt-1 truncate text-sm font-medium text-[var(--fg)]">{value}</p>
    </div>
  );
}

export function InstrumentDetail({ code }: { code: string }) {
  const symbol = code.trim();
  const sessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    retry: false,
    refetchInterval: TRADER_POLL_MS,
  });
  const session = asRecord(sessionQ.data);
  const connection = resolveConnectionPresentation(session);
  const live = isLiveBrokerCatalogue(session);
  const mismatch = connection.state === "ACCOUNT_SESSION_MISMATCH";
  const noBroker = connection.state === "BROKER_NOT_CONNECTED";

  const universeQ = useQuery({
    queryKey: MARKET_UNIVERSE_QUERY_KEY,
    queryFn: () => marketUniverseApi.snapshot(),
    enabled: connection.connected && !mismatch && live && Boolean(symbol),
    retry: false,
    refetchInterval: UNIVERSE_POLL_MS,
  });

  const universe = asRecord(universeQ.data);
  const instruments = asList(universe.instruments).map(asRecord);
  const source = str(universe.catalogue_source);
  const rows =
    source === "LIVE_BROKER"
      ? mergeCatalogueRows(
          instruments,
          asList(asRecord(universe.opportunity_board).rows).map(asRecord),
        )
      : [];
  const row =
    rows.find((item) => {
      const key = str(item.broker_symbol, str(item.symbol, str(item.canonical_symbol)));
      return key.toUpperCase() === symbol.toUpperCase();
    }) ?? null;

  const unavailable =
    noBroker ||
    mismatch ||
    !live ||
    universeQ.isError ||
    (universeQ.isFetched && source !== "LIVE_BROKER");

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        title={symbol || "Instrument"}
        description={instrumentName(row ?? { broker_symbol: symbol })}
        actions={
          <>
            <Button variant="secondary" asChild>
              <Link href="/markets">Markets</Link>
            </Button>
            <Button variant="secondary" asChild>
              <Link href="/terminal">Terminal</Link>
            </Button>
          </>
        }
      />
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--fg-subtle)]">
        {RESEARCH_NOT_AUTHORIZATION}
      </p>

      {sessionQ.isLoading || universeQ.isLoading ? (
        <DeskSkeleton rows={4} />
      ) : unavailable ? (
        <DeskEmpty
          icon={Activity}
          title="CATALOGUE UNAVAILABLE"
          description="Broker market catalogue is currently unavailable. This is not an empty instrument."
          actionLabel="Open Markets"
          actionHref="/markets"
        />
      ) : !row ? (
        <DeskEmpty
          icon={Activity}
          title="Instrument not in catalogue"
          description="This symbol is not in your live broker catalogue."
          actionLabel="Open Markets"
          actionHref="/markets"
        />
      ) : (
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>{str(row.broker_symbol, symbol)}</CardTitle>
            <Badge>{str(row.asset_class, "UNKNOWN")}</Badge>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Cell label="Asset class" value={str(row.asset_class, "UNKNOWN")} />
            <Cell label="Trading status" value={marketDataState(row)} />
            <Cell label="Session" value={rowSession(row)} />
            <Cell label="Regime" value={rowRegime(row)} />
            <Cell label="Direction" value={rowDirection(row)} />
            <Cell label="Opportunity" value={scoreDisplay(row.opportunity_score)} />
            <Cell label="Edge" value={scoreDisplay(row.directional_edge ?? row.edge)} />
            <Cell label="Risk/Reward" value={scoreDisplay(row.RR ?? row.rr)} />
            <Cell label="Freshness" value={signalFreshness(row)} />
            <Cell label="Bid" value={priceDisplay(row.bid)} />
            <Cell label="Ask" value={priceDisplay(row.ask)} />
            <Cell label="Spread" value={numericDisplay(row.spread)} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
