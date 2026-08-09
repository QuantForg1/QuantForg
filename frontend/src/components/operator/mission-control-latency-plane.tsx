"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import {
  institutionalObservabilityApi,
  iteReliabilityApi,
  platformApi,
} from "@/lib/api/endpoints";
import { listApiRequestSamples } from "@/lib/api/request-log";
import { asRecord, num } from "@/lib/desk";
import { useTradingSession } from "@/providers/trading-session-provider";
import { formatNumber } from "@/lib/utils";

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-[var(--border)] bg-[var(--bg)] px-2 py-2">
      <p className="text-[9px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p className="mt-1 font-mono text-[12px] tabular text-[var(--fg)]">{value}</p>
    </div>
  );
}

/** Mission Control V2 — resource & latency plane from LIVE observability. */
export function MissionControlLatencyPlane() {
  const session = useTradingSession();
  const healthQ = useQuery({
    queryKey: ["platform-health-live"],
    queryFn: platformApi.healthLive,
    staleTime: 45_000,
    refetchInterval: 60_000,
    retry: 1,
  });
  const latQ = useQuery({
    queryKey: ["institutional-observability-latency", "mc-v2"],
    queryFn: institutionalObservabilityApi.latency,
    staleTime: 60_000,
    refetchInterval: 90_000,
    retry: false,
  });
  const resQ = useQuery({
    queryKey: ["institutional-observability-resources", "mc-v2"],
    queryFn: institutionalObservabilityApi.resources,
    staleTime: 60_000,
    refetchInterval: 90_000,
    retry: false,
  });
  const relQ = useQuery({
    queryKey: ["ite-rel-metrics", "mc-v2"],
    queryFn: iteReliabilityApi.metrics,
    staleTime: 60_000,
    refetchInterval: 120_000,
    retry: false,
  });

  const lat = asRecord(latQ.data);
  const resources = asRecord(resQ.data);
  const rel = asRecord(relQ.data);
  const merged = { ...asRecord(rel.resources), ...resources, ...lat };

  const apiAvg = useMemo(() => {
    const samples = listApiRequestSamples().slice(0, 25);
    if (!samples.length) return null;
    return Math.round(
      samples.reduce((s, r) => s + r.latencyMs, 0) / samples.length,
    );
  }, [healthQ.dataUpdatedAt, latQ.dataUpdatedAt]);

  const ms = (v: unknown) => {
    const n = num(v, NaN);
    return Number.isFinite(n) ? `${Math.round(n)} ms` : "—";
  };
  const mb = (v: unknown) => {
    const n = num(v, NaN);
    return Number.isFinite(n) ? `${formatNumber(n, 0)} MB` : "—";
  };
  const pct = (v: unknown) => {
    const n = num(v, NaN);
    return Number.isFinite(n) ? `${formatNumber(n, 1)}%` : "—";
  };

  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Mission Control V2 · Resources & latency
        </h2>
        <Badge tone="neutral" className="h-5 px-1.5 text-[10px]">
          LIVE observe
        </Badge>
      </header>
      <div className="grid gap-2 p-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        <Cell label="Memory" value={mb(merged.memory_mb ?? merged.memory)} />
        <Cell label="CPU" value={pct(merged.cpu_pct ?? merged.cpu)} />
        <Cell label="API Latency" value={apiAvg != null ? `${apiAvg} ms` : ms(merged.api_latency_ms)} />
        <Cell
          label="Gateway Latency"
          value={
            Number.isFinite(num(session.latencyMs, NaN))
              ? `${Math.round(num(session.latencyMs))} ms`
              : ms(merged.gateway_latency_ms)
          }
        />
        <Cell label="Broker Latency" value={ms(merged.broker_latency_ms ?? merged.mt5_latency_ms)} />
        <Cell label="Scanner Latency" value={ms(merged.scanner_latency_ms)} />
        <Cell label="OMS Latency" value={ms(merged.oms_latency_ms)} />
        <Cell label="Risk Latency" value={ms(merged.risk_latency_ms)} />
        <Cell label="PME Latency" value={ms(merged.pme_latency_ms)} />
        <Cell label="Database Latency" value={ms(merged.database_latency_ms ?? merged.db_latency_ms)} />
        <Cell
          label="Health Probe Age"
          value={
            healthQ.dataUpdatedAt
              ? `${Math.max(0, Math.round((Date.now() - healthQ.dataUpdatedAt) / 1000))} s ago`
              : "—"
          }
        />
        <Cell
          label="Obs Feed"
          value={latQ.isSuccess || resQ.isSuccess ? "Ready" : latQ.isError ? "Partial" : "…"}
        />
      </div>
      <p className="border-t border-[var(--border)] px-3 py-1.5 text-[10px] text-[var(--fg-subtle)]">
        Missing latencies stay “—” until observability endpoints publish them — never fabricated.
      </p>
    </section>
  );
}
