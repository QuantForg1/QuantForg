"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { PageMotion } from "@/components/desk/motion";
import { DeskQueryState } from "@/components/desk/query-state";
import { SessionStrip } from "@/components/broker/session-strip";
import { ExposureMap } from "@/components/book/exposure-map";
import { BookEmpty } from "@/components/book/empty-state";
import { useTradingSession } from "@/providers/trading-session-provider";
import { portfolioApi, portfolioIntelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, metric, num } from "@/lib/desk";

export default function ExposurePage() {
  const session = useTradingSession();
  const portfolioQ = useQuery({
    queryKey: ["portfolio"],
    queryFn: portfolioApi.get,
    retry: false,
    staleTime: 12_000,
    enabled: session.connected,
  });
  const intelQ = useQuery({
    queryKey: ["portfolio-intelligence-dashboard"],
    queryFn: () => portfolioIntelligenceApi.dashboard(0.95),
    retry: false,
    staleTime: 30_000,
  });

  const account = asRecord(portfolioQ.data?.account);
  const positions = useMemo(() => {
    const fromApi = asList(portfolioQ.data?.positions).map(asRecord);
    return fromApi.length ? fromApi : session.positions;
  }, [portfolioQ.data, session.positions]);

  const freeMargin = metric(account, "free_margin") || num(session.freeMargin);
  const intelligence = intelQ.data ? asRecord(intelQ.data) : null;

  return (
    <div>
      <PageHeader
        title="Exposure"
        description="Symbol and asset-class heat from live positions."
        actions={
          <Button asChild size="sm" variant="secondary">
            <Link href="/portfolio">Portfolio OS</Link>
          </Button>
        }
      />
      <SessionStrip className="mb-4" />
      <DeskQueryState
        isLoading={session.connected && portfolioQ.isLoading}
        isError={session.connected && portfolioQ.isError}
        errorMessage="Unable to load exposure."
        onRetry={() => portfolioQ.refetch()}
        skeleton="chart"
      >
        <PageMotion>
          {!session.connected ? (
            <BookEmpty
              title="No live exposure"
              description="Attach MT5 in Broker to map symbol and class exposure from real positions."
              action={
                <Button size="sm" variant="secondary" asChild>
                  <Link href="/broker">Open Broker</Link>
                </Button>
              }
            />
          ) : (
            <div className="min-h-[480px]">
              <ExposureMap
                positions={positions}
                freeMargin={Number.isFinite(freeMargin) ? freeMargin : 0}
                intelligence={intelligence}
                focused
              />
            </div>
          )}
        </PageMotion>
      </DeskQueryState>
    </div>
  );
}
