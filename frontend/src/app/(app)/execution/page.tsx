"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { ConnectionBar } from "@/components/execution/connection-bar";
import { MarketWatch } from "@/components/execution/market-watch";
import { ExecutionOrderTicket } from "@/components/execution/order-ticket";
import { PositionManager } from "@/components/execution/position-manager";
import { OrdersWorkspace } from "@/components/execution/orders-workspace";
import { PageMotion } from "@/components/desk/motion";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { RealtimeConnectionBadge, RealtimeMeta } from "@/components/realtime/connection-badge";
import { useExecutionStream } from "@/hooks/realtime";
import { mt5Api } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";

export default function ExecutionPage() {
  const [symbol, setSymbol] = useState("EURUSD");
  const realtime = useExecutionStream(symbol);

  const statusQ = useQuery({
    queryKey: ["mt5-status"],
    queryFn: mt5Api.status,
    retry: false,
  });

  const symbolsQ = useQuery({
    queryKey: ["mt5-symbols"],
    queryFn: mt5Api.symbols,
    retry: false,
    enabled: Boolean(statusQ.data?.connected),
  });

  const tickQ = useQuery({
    queryKey: ["mt5-tick", symbol],
    queryFn: () => mt5Api.tick(symbol),
    retry: false,
    enabled: Boolean(statusQ.data?.connected) && Boolean(symbol),
  });

  const connected = Boolean(statusQ.data?.connected);
  const tick = asRecord(tickQ.data);
  const fromSymbols = useMemo(() => {
    const hit = asList(symbolsQ.data)
      .map(asRecord)
      .find((s) => str(s.code) === symbol);
    return hit ?? {};
  }, [symbolsQ.data, symbol]);

  const bid = num(tick.bid, num(fromSymbols.bid));
  const ask = num(tick.ask, num(fromSymbols.ask));

  return (
    <div>
      <PageHeader
        title="Execution Center"
        description="Institutional trading terminal — market watch, order ticket, positions, and pending orders via existing MT5 + execution gateway APIs."
        actions={<RealtimeConnectionBadge status={realtime} />}
      />
      <RealtimeMeta status={realtime} className="mb-3" />

      {statusQ.isLoading ? (
        <DeskSkeleton variant="page" />
      ) : statusQ.isError ? (
        <DeskError
          message="Unable to load MT5 connection status."
          onRetry={() => statusQ.refetch()}
        />
      ) : (
        <PageMotion className="space-y-4">
          <ConnectionBar
            connected={connected}
            server={statusQ.data?.server}
            login={statusQ.data?.login}
            latencyMs={realtime.latencyMs ?? statusQ.data?.latency_ms}
            tradingEnabled={connected}
          />

          <div className="grid gap-4 xl:grid-cols-[0.95fr_1.15fr]">
            <MarketWatch connected={connected} selected={symbol} onSelect={setSymbol} />
            <ExecutionOrderTicket
              symbol={symbol}
              onSymbolChange={setSymbol}
              connected={connected}
              bid={Number.isFinite(bid) ? bid : undefined}
              ask={Number.isFinite(ask) ? ask : undefined}
            />
          </div>

          <PositionManager connected={connected} />
          <OrdersWorkspace connected={connected} />
        </PageMotion>
      )}
    </div>
  );
}
