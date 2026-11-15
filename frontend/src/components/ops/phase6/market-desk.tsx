"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { institutionalIntelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import {
  Phase6Banner,
  Phase6Empty,
  Phase6Error,
  Phase6Loading,
  Phase6ModuleNav,
  Phase6Stat,
  Phase6TabBar,
} from "./shared";

type Tab = "regime" | "forecast" | "quality";

const TABS: { id: Tab; label: string }[] = [
  { id: "regime", label: "Regime" },
  { id: "forecast", label: "Forecast" },
  { id: "quality", label: "Data quality" },
];

export function Phase6MarketDesk() {
  const [tab, setTab] = useState<Tab>("regime");
  const q = useQuery({
    queryKey: ["p6-market", TRADING_SYMBOL],
    queryFn: () =>
      institutionalIntelligenceApi.market({
        symbol: TRADING_SYMBOL,
        regime_label: "ranging",
        regime_confidence: 70,
      }),
    retry: false,
    staleTime: 15_000,
  });

  if (q.isLoading) return <Phase6Loading />;
  if (q.isError) {
    return <Phase6Error message="Predictive market overview unavailable." />;
  }

  const data = asRecord(q.data);
  const regime = asRecord(data.regime);
  const forecast = asRecord(data.forecast);
  const dq = asRecord(data.data_quality);
  const missing = asList(dq.missing_fields);
  const limitations = asList(forecast.limitations);

  return (
    <div>
      <Phase6ModuleNav current="/predictive-market-intelligence" />
      <Phase6Banner tone="warn">
        Predictions are not guaranteed outcomes. Confidence and limitations are
        shown explicitly. Missing liquidity or OHLC is never invented.
      </Phase6Banner>
      <Phase6TabBar tabs={TABS} value={tab} onChange={setTab} />

      {tab === "regime" && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Phase6Stat label="Symbol" value={str(data.symbol) || TRADING_SYMBOL} />
          <Phase6Stat label="Regime" value={str(regime.regime)} />
          <Phase6Stat label="Confidence" value={str(regime.confidence)} />
          <Phase6Stat label="Model" value={str(data.model_version)} />
        </div>
      )}

      {tab === "forecast" &&
        (!data.forecast ? (
          <Phase6Empty message="Forecast unavailable — insufficient evidence." />
        ) : (
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Phase6Stat label="Horizon" value={str(forecast.horizon)} />
              <Phase6Stat label="Bias" value={str(forecast.direction_bias)} />
              <Phase6Stat label="Confidence" value={str(forecast.confidence)} />
              <Phase6Stat
                label="Guarantees outcome"
                value={forecast.guarantees_outcome === true ? "yes" : "no"}
              />
            </div>
            <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
              {limitations.map((l, i) => (
                <li key={i}>{str(l) || String(l)}</li>
              ))}
            </ul>
          </div>
        ))}

      {tab === "quality" && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Phase6Stat label="Source" value={str(dq.source)} />
          <Phase6Stat label="As of" value={str(dq.as_of)} />
          <Phase6Stat label="Stale" value={dq.stale === true ? "yes" : "no"} />
          <Phase6Stat
            label="Missing"
            value={missing.length ? missing.map((m) => str(m)).join(", ") : "none"}
          />
        </div>
      )}
    </div>
  );
}
