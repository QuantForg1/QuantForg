"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { StatCard } from "@/components/dashboard/stat-card";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { WeltradeGatewayStatus } from "@/components/desk/weltrade-gateway-status";
import { ExecutionMetricsStrip } from "@/components/execution/execution-metrics-strip";
import { loadLastExecutionMetrics } from "@/lib/execution/last-metrics";
import { mt5Api, platformApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";

const IteReliabilityPanel = dynamic(
  () =>
    import("@/components/ops/ite-reliability-panel").then(
      (m) => m.IteReliabilityPanel,
    ),
  {
    ssr: false,
    loading: () => <DeskSkeleton rows={4} />,
  },
);

function lat(v: unknown): string {
  const n = num(v);
  return Number.isFinite(n) ? `${formatNumber(n, 0)} ms` : "";
}

export default function MonitoringPage() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: platformApi.health,
    retry: false,
    refetchInterval: 30_000,
  });
  const mt5 = useQuery({
    queryKey: ["mt5-status"],
    queryFn: mt5Api.status,
    retry: false,
    refetchInterval: 30_000,
  });

  const execMetrics = useMemo(() => loadLastExecutionMetrics(), []);

  const deps = asList(asRecord(health.data).dependencies).map(asRecord);
  const findDep = (name: string) =>
    deps.find((d) => str(d.name).toLowerCase().includes(name.toLowerCase()));
  const db = findDep("postgres") || findDep("database");
  const redis = findDep("redis");

  return (
    <div>
      <PageHeader
        title="Monitoring"
        description="Gateway health, execution latency, and reliability. Full control plane remains on Ops."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/ops">Ops</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />

      <PageMotion className="space-y-4">
        <WeltradeGatewayStatus />

        <ExecutionMetricsStrip metrics={execMetrics} />

        {health.isLoading && mt5.isLoading ? (
          <DeskSkeleton variant="kpis" rows={4} />
        ) : health.isError && mt5.isError ? (
          <DeskError
            message="Unable to load health."
            onRetry={() => {
              void health.refetch();
              void mt5.refetch();
            }}
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="API health"
              value={str(asRecord(health.data).status, "—")}
              hint={str(asRecord(health.data).environment, "")}
            />
            <StatCard
              label="Broker / MT5"
              value={
                asRecord(mt5.data).connected
                  ? "connected"
                  : mt5.isError
                    ? "error"
                    : "disconnected"
              }
              hint={lat(asRecord(mt5.data).latency_ms)}
            />
            <StatCard
              label="Database"
              value={str(asRecord(db).status, "—")}
              hint={lat(asRecord(db).latency_ms)}
            />
            <StatCard
              label="Redis"
              value={str(asRecord(redis).status, "—")}
              hint={lat(asRecord(redis).latency_ms)}
            />
          </div>
        )}

        <IteReliabilityPanel />
      </PageMotion>
    </div>
  );
}
