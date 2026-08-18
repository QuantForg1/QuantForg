"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Flame } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  institutionalObservabilityApi,
  iteOpsApi,
  iteReliabilityApi,
  platformApi,
  signalCenterApi,
} from "@/lib/api/endpoints";
import { listApiRequestSamples } from "@/lib/api/request-log";
import { asList, asRecord, num, str } from "@/lib/desk";
import { useLiveTrades } from "@/hooks/use-live-trades";
import {
  burnInSamplesCsv,
  latestBurnInSample,
  listBurnInSamples,
  recordBurnInSample,
} from "@/lib/operator/burnin-metrics";
import { downloadText } from "@/lib/operator/export";
import { useTradingSession } from "@/providers/trading-session-provider";
import { useAuth } from "@/providers/auth-provider";
import { formatNumber } from "@/lib/utils";

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-[var(--border)]/70 bg-[var(--bg)] px-2 py-1.5">
      <p className="text-[9px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p className="mt-0.5 font-mono text-[12px] tabular text-[var(--fg)]">{value}</p>
    </div>
  );
}

/**
 * RC2 continuous observation strip — samples LIVE desks into a local history ring.
 * Read-only. No Trading Core / OMS / Gateway mutations.
 */
export function Rc2BurnInPanel() {
  const session = useTradingSession();
  const { opsReady } = useAuth();
  const { trades, analytics } = useLiveTrades("today");
  const [tick, setTick] = useState(0);
  const lastSampleAt = useRef(0);

  const healthQ = useQuery({
    queryKey: ["platform-health", "rc2-burnin"],
    queryFn: platformApi.health,
    staleTime: 45_000,
    refetchInterval: 60_000,
    retry: 1,
  });
  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading", "rc2-burnin"],
    queryFn: iteOpsApi.autoTrading,
    enabled: opsReady,
    staleTime: 45_000,
    refetchInterval: opsReady ? 60_000 : false,
    retry: false,
  });
  const signalsQ = useQuery({
    queryKey: ["signals-center", "rc2-burnin"],
    queryFn: () => signalCenterApi.list({}),
    enabled: opsReady,
    staleTime: 45_000,
    refetchInterval: opsReady ? 90_000 : false,
    retry: false,
  });
  const obsQ = useQuery({
    queryKey: ["institutional-observability-latency", "rc2-burnin"],
    queryFn: institutionalObservabilityApi.latency,
    enabled: opsReady,
    staleTime: 60_000,
    refetchInterval: opsReady ? 120_000 : false,
    retry: false,
  });
  const relQ = useQuery({
    queryKey: ["ite-rel-metrics", "rc2-burnin"],
    queryFn: iteReliabilityApi.metrics,
    enabled: opsReady,
    staleTime: 60_000,
    refetchInterval: opsReady ? 120_000 : false,
    retry: false,
  });

  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), 30_000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    const now = Date.now();
    if (now - lastSampleAt.current < 55_000) return;
    lastSampleAt.current = now;

    const closed = trades.filter((t) => t.status === "closed");
    const hourAgo = now - 3_600_000;
    const tradesHour = closed.filter((t) => t.time.getTime() >= hourAgo).length;
    const apiSamples = listApiRequestSamples();
    const avgApi =
      apiSamples.length > 0
        ? Math.round(
            apiSamples.slice(0, 20).reduce((s, r) => s + r.latencyMs, 0) /
              Math.min(20, apiSamples.length),
          )
        : null;

    const auto = asRecord(autoQ.data);
    const live = asRecord(auto.live);
    const dash = asRecord(asRecord(signalsQ.data).dashboard);
    const obs = asRecord(obsQ.data);
    const rel = asRecord(relQ.data);
    const resources = asRecord(obs.resources || rel.resources || rel);

    const journalish = asList(session.orders);
    const submitted = journalish.length;
    const accepted = journalish.filter((o) =>
      /accept|filled|done|live/i.test(str(asRecord(o).status)),
    ).length;
    const rejected = journalish.filter((o) =>
      /reject|denied|fail/i.test(str(asRecord(o).status)),
    ).length;

    recordBurnInSample({
      tradesDay: closed.length,
      tradesHour,
      winRate: analytics.winRate,
      profitFactor: analytics.profitFactor,
      avgRr: analytics.averageRr,
      avgHoldMs: analytics.avgHoldMs,
      eligibleSymbols: (() => {
        const n0 = num(
          asRecord(asRecord(auto.ai_scalping).scan).eligible_count ??
            dash.enabled_symbols,
          NaN,
        );
        return Number.isFinite(n0) ? n0 : null;
      })(),
      ordersSubmitted: submitted || null,
      ordersAccepted: accepted || null,
      ordersRejected: rejected || null,
      apiLatencyMs: avgApi,
      dashboardLatencyMs: healthQ.dataUpdatedAt
        ? Math.max(0, Date.now() - healthQ.dataUpdatedAt)
        : avgApi,
      scannerLatencyMs: (() => {
        const n0 = num(obs.scanner_latency_ms ?? live.scanner_latency_ms, NaN);
        return Number.isFinite(n0) ? n0 : null;
      })(),
      omsLatencyMs: (() => {
        const n0 = num(obs.oms_latency_ms ?? live.oms_latency_ms, NaN);
        return Number.isFinite(n0) ? n0 : null;
      })(),
      pmeLatencyMs: (() => {
        const n0 = num(obs.pme_latency_ms ?? live.pme_latency_ms, NaN);
        return Number.isFinite(n0) ? n0 : null;
      })(),
      memoryMb: (() => {
        const n0 = num(resources.memory_mb ?? resources.memory, NaN);
        return Number.isFinite(n0) ? n0 : null;
      })(),
      cpuPct: (() => {
        const n0 = num(resources.cpu_pct ?? resources.cpu, NaN);
        return Number.isFinite(n0) ? n0 : null;
      })(),
      gatewayOnline: session.healthKnown ? session.gatewayOnline : null,
      brokerOnline: session.healthKnown ? session.brokerConnected : null,
    });
    setTick((t) => t + 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sample on interval + key feed updates
  }, [
    tick,
    trades,
    analytics.winRate,
    analytics.profitFactor,
    autoQ.data,
    signalsQ.data,
    obsQ.data,
    relQ.data,
    healthQ.dataUpdatedAt,
    session.gatewayOnline,
    session.brokerConnected,
    session.healthKnown,
    session.orders,
  ]);

  const latest = useMemo(() => latestBurnInSample(), [tick]);
  const historyN = listBurnInSamples().length;

  const fmt = (v: number | null | undefined, digits = 2) =>
    v == null || !Number.isFinite(v) ? "—" : formatNumber(v, digits);
  const pct = (v: number | null | undefined) =>
    v == null || !Number.isFinite(v) ? "—" : `${(v * 100).toFixed(1)}%`;

  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <div className="flex items-center gap-2">
          <Flame className="h-3.5 w-3.5 text-[var(--accent)]" aria-hidden />
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            RC2 Live Burn-in
          </h2>
          <Badge tone="success" className="h-5 px-1.5 text-[10px]">
            Observing
          </Badge>
          <span className="text-[10px] text-[var(--fg-subtle)]">
            {historyN} samples stored locally
          </span>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() =>
            downloadText(
              `quantforg-rc2-burnin-${Date.now()}.csv`,
              burnInSamplesCsv(listBurnInSamples()),
              "text/csv",
            )
          }
          disabled={!historyN}
        >
          <Download className="mr-1 h-3.5 w-3.5" />
          Export history
        </Button>
      </header>
      <div className="grid gap-2 p-3 sm:grid-cols-3 lg:grid-cols-6 xl:grid-cols-9">
        <Cell label="Trades/day" value={fmt(latest?.tradesDay, 0)} />
        <Cell label="Trades/hour" value={fmt(latest?.tradesHour, 0)} />
        <Cell label="Win Rate" value={pct(latest?.winRate)} />
        <Cell label="Profit Factor" value={fmt(latest?.profitFactor)} />
        <Cell label="Avg RR" value={fmt(latest?.avgRr)} />
        <Cell
          label="Avg Hold"
          value={
            latest?.avgHoldMs != null
              ? `${Math.round(latest.avgHoldMs / 60000)}m`
              : "—"
          }
        />
        <Cell label="Eligible Sym" value={fmt(latest?.eligibleSymbols, 0)} />
        <Cell label="Orders Acc" value={fmt(latest?.ordersAccepted, 0)} />
        <Cell label="Orders Rej" value={fmt(latest?.ordersRejected, 0)} />
        <Cell label="GW Reconnects" value={fmt(latest?.gatewayReconnects, 0)} />
        <Cell label="Broker Reconn" value={fmt(latest?.brokerReconnects, 0)} />
        <Cell label="API Latency" value={latest?.apiLatencyMs != null ? `${latest.apiLatencyMs} ms` : "—"} />
        <Cell
          label="Dash Latency"
          value={
            latest?.dashboardLatencyMs != null
              ? `${latest.dashboardLatencyMs} ms`
              : "—"
          }
        />
        <Cell
          label="Scanner Lat"
          value={
            latest?.scannerLatencyMs != null
              ? `${Math.round(latest.scannerLatencyMs)} ms`
              : "—"
          }
        />
        <Cell
          label="OMS Lat"
          value={
            latest?.omsLatencyMs != null
              ? `${Math.round(latest.omsLatencyMs)} ms`
              : "—"
          }
        />
        <Cell
          label="PME Lat"
          value={
            latest?.pmeLatencyMs != null
              ? `${Math.round(latest.pmeLatencyMs)} ms`
              : "—"
          }
        />
        <Cell label="Memory" value={latest?.memoryMb != null ? `${fmt(latest.memoryMb, 0)} MB` : "—"} />
        <Cell label="CPU" value={latest?.cpuPct != null ? `${fmt(latest.cpuPct, 1)}%` : "—"} />
      </div>
      <p className="border-t border-[var(--border)] px-3 py-1.5 text-[10px] text-[var(--fg-subtle)]">
        Samples every ~60s from LIVE history / ops / observability. Missing fields stay “—” — never fabricated.
      </p>
    </section>
  );
}
