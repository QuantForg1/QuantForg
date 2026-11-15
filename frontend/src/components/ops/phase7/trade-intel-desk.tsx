"use client";

import { useQuery } from "@tanstack/react-query";
import { autonomousTradingControlApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import {
  Phase7Banner,
  Phase7Empty,
  Phase7Error,
  Phase7Loading,
  Phase7ModuleNav,
  Phase7Stat,
  Phase7TabBar,
} from "./shared";
import { useState } from "react";

type Tab = "trades" | "feedback" | "orders";

const TABS: { id: Tab; label: string }[] = [
  { id: "trades", label: "Post-trade" },
  { id: "orders", label: "Order lifecycle" },
  { id: "feedback", label: "Feedback" },
];

export function Phase7TradeIntelDesk() {
  const [tab, setTab] = useState<Tab>("trades");
  const trades = useQuery({
    queryKey: ["p7-trades"],
    queryFn: autonomousTradingControlApi.tradeIntelligence,
    retry: false,
    staleTime: 15_000,
  });
  const orders = useQuery({
    queryKey: ["p7-orders"],
    queryFn: autonomousTradingControlApi.ordersLifecycle,
    retry: false,
    staleTime: 15_000,
  });
  const feedback = useQuery({
    queryKey: ["p7-feedback"],
    queryFn: autonomousTradingControlApi.feedback,
    retry: false,
    staleTime: 15_000,
  });

  if (trades.isLoading) return <Phase7Loading />;
  if (trades.isError) {
    return <Phase7Error message="Trade intelligence unavailable." />;
  }

  const t = asRecord(trades.data);
  const tradeRows = asList(t.trades);
  const orderRows = asList(asRecord(orders.data).orders);
  const fb = asRecord(feedback.data);

  return (
    <div>
      <Phase7ModuleNav current="/trade-intelligence" />
      <Phase7Banner tone="neutral">
        Post-trade analysis uses confirmed fills only. Unconfirmed orders are
        not classified as completed trades. Execution quality is separated from
        strategy quality. No fabricated P&amp;L.
      </Phase7Banner>
      <Phase7TabBar tabs={TABS} value={tab} onChange={setTab} />
      {tab === "trades" ? (
        <>
          <div className="mb-4 grid gap-3 sm:grid-cols-3">
            <Phase7Stat label="Analyzed" value={Number(t.count || 0)} />
            <Phase7Stat
              label="Fabricated"
              value={t.fabricated === true ? "yes" : "no"}
            />
            <Phase7Stat
              label="Empty"
              value={t.empty === true ? "yes" : "no"}
            />
          </div>
          {tradeRows.length === 0 ? (
            <Phase7Empty message="No confirmed trades available for analysis." />
          ) : (
            <div className="space-y-2">
              {tradeRows.map((item, i) => {
                const row = asRecord(item);
                return (
                  <div
                    key={i}
                    className="rounded-md border border-border/60 px-3 py-2 font-mono text-xs"
                  >
                    {str(row.classification)} · {str(row.symbol)} ·{" "}
                    {str(row.id)}
                  </div>
                );
              })}
            </div>
          )}
        </>
      ) : null}
      {tab === "orders" ? (
        orderRows.length === 0 ? (
          <Phase7Empty message="No OMS journal rows available (read-only compose)." />
        ) : (
          <div className="space-y-2">
            {orderRows.map((item, i) => {
              const row = asRecord(item);
              return (
                <div
                  key={i}
                  className="rounded-md border border-border/60 px-3 py-2 font-mono text-xs"
                >
                  {str(row.status)} · {str(row.symbol)} · {str(row.id)}
                </div>
              );
            })}
          </div>
        )
      ) : null}
      {tab === "feedback" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <Phase7Stat
            label="Calibration"
            value={str(asRecord(fb.calibration).status) || "unavailable"}
          />
          <Phase7Stat
            label="Drift"
            value={str(asRecord(fb.drift).status) || "unavailable"}
          />
          <Phase7Stat
            label="Auto model→LIVE"
            value="blocked"
            hint="Training separated from production execution"
          />
          <Phase7Stat
            label="Fabricated training"
            value="forbidden"
          />
        </div>
      ) : null}
    </div>
  );
}
