"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { LazyBarChart } from "@/components/charts/lazy";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { PageMotion } from "@/components/desk/motion";
import { opsApi, platformApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";

function toneFor(status: string): "success" | "warning" | "danger" | "accent" | "neutral" {
  const s = status.toLowerCase();
  if (s === "healthy" || s === "ok" || s === "up") return "success";
  if (s === "degraded" || s === "alive") return "accent";
  if (s === "unhealthy" || s === "down" || s === "error") return "danger";
  if (s === "unknown") return "warning";
  return "neutral";
}

export default function OpsPage() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: platformApi.health,
    retry: false,
  });
  const dashboard = useQuery({
    queryKey: ["ops-dashboard"],
    queryFn: opsApi.dashboard,
    retry: false,
  });
  const metrics = useQuery({
    queryKey: ["ops-metrics"],
    queryFn: opsApi.metrics,
    retry: false,
  });

  const deps = asList(health.data?.dependencies).map(asRecord);
  const components = asList(dashboard.data?.components).map(asRecord);
  const m = asRecord(metrics.data);
  const latencySeries = [
    ...deps.map((d) => ({ label: str(d.name), value: num(d.latency_ms, 0) })),
    ...components.map((c) => ({
      label: str(c.kind),
      value: num(c.latency_ms, 0),
    })),
  ].slice(0, 12);

  const findDep = (name: string) =>
    deps.find((d) => str(d.name).toLowerCase().includes(name.toLowerCase()));
  const findComp = (kind: string) =>
    components.find((c) => str(c.kind).toLowerCase() === kind.toLowerCase());

  const db = findDep("postgres") || findDep("database") || findComp("database");
  const redis = findDep("redis") || findComp("queue");
  const api = findComp("api") || { status: health.data?.status, latency_ms: null };
  const railway = findComp("system") || { status: health.data?.environment, latency_ms: null };

  return (
    <div>
      <PageHeader
        title="Operations"
        description="System health, infrastructure latency, and admin monitoring."
      />

      {health.isLoading ? (
        <DeskSkeleton variant="page" />
      ) : health.isError ? (
        <DeskError message="Unable to load health." onRetry={() => health.refetch()} />
      ) : (
        <PageMotion>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
            <StatCard
              label="System Health"
              value={str(dashboard.data?.overall ?? health.data?.status, "—")}
              hint={str(health.data?.version, "")}
            />
            <StatCard
              label="Database"
              value={str(asRecord(db).status, "—")}
              hint={lat(asRecord(db).latency_ms)}
            />
            <StatCard
              label="Redis"
              value={str(asRecord(redis).status, "disabled")}
              hint={lat(asRecord(redis).latency_ms)}
            />
            <StatCard
              label="Railway"
              value={str(health.data?.environment ?? asRecord(railway).status, "—")}
            />
            <StatCard label="API" value={str(asRecord(api).status ?? health.data?.status, "—")} />
            <StatCard
              label="Avg Latency"
              value={
                Number.isFinite(num(m.request_latency_ms_avg))
                  ? `${formatNumber(num(m.request_latency_ms_avg), 1)} ms`
                  : lat(asRecord(api).latency_ms)
              }
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>Response times</CardTitle>
                <Badge tone={toneFor(str(health.data?.status))}>
                  {str(health.data?.status)}
                </Badge>
              </CardHeader>
              <CardContent>
                <LazyBarChart data={latencySeries} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Dependencies</CardTitle>
              </CardHeader>
              <CardContent>
                {deps.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">No dependency probes returned.</p>
                ) : (
                  <DeskTable
                    columns={["Name", "Status", "Latency"]}
                    rows={deps.map((d) => [
                      str(d.name),
                      <Badge key="s" tone={toneFor(str(d.status))}>
                        {str(d.status)}
                      </Badge>,
                      lat(d.latency_ms),
                    ])}
                  />
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Ops dashboard</CardTitle>
              </CardHeader>
              <CardContent>
                {dashboard.isLoading ? (
                  <DeskSkeleton rows={2} />
                ) : dashboard.isError ? (
                  <DeskError message="Ops dashboard requires owner/admin. Non-admin sessions receive 401/403 by design." />
                ) : (
                  <>
                    <div className="mb-3 flex flex-wrap gap-2">
                      <Badge tone={toneFor(str(dashboard.data?.overall))}>
                        {str(dashboard.data?.overall)}
                      </Badge>
                      <Badge tone={dashboard.data?.execution_enabled ? "danger" : "neutral"}>
                        Execution {dashboard.data?.execution_enabled ? "ON" : "OFF"}
                      </Badge>
                      <span className="text-xs text-[var(--fg-subtle)]">
                        Collected {str(dashboard.data?.collected_at).slice(0, 19)}
                      </span>
                    </div>
                    <DeskTable
                      columns={["Component", "Status", "Latency", "Detail"]}
                      rows={components.map((c) => [
                        str(c.kind),
                        <Badge key="s" tone={toneFor(str(c.status))}>
                          {str(c.status)}
                        </Badge>,
                        lat(c.latency_ms),
                        str(c.detail).slice(0, 48),
                      ])}
                    />
                  </>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Metrics</CardTitle>
              </CardHeader>
              <CardContent>
                {metrics.isLoading ? (
                  <DeskSkeleton rows={2} />
                ) : metrics.isError ? (
                  <p className="text-sm text-[var(--fg-muted)]">
                    Metrics endpoint restricted to privileged operators.
                  </p>
                ) : (
                  <DeskTable
                    columns={["Metric", "Value"]}
                    rows={[
                      ["Request latency avg", lat(m.request_latency_ms_avg)],
                      ["Error rate", Number.isFinite(num(m.error_rate)) ? formatNumber(num(m.error_rate), 4) : "—"],
                      ["Throughput / min", str(m.throughput_per_minute, "—")],
                      ["Cache hit ratio", Number.isFinite(num(m.cache_hit_ratio)) ? formatNumber(num(m.cache_hit_ratio), 3) : "—"],
                      ["Requests", str(m.request_count, "—")],
                      ["Errors", str(m.error_count, "—")],
                    ].map(([a, b]) => [a, b])}
                  />
                )}
              </CardContent>
            </Card>
          </div>
        </PageMotion>
      )}
    </div>
  );
}

function lat(v: unknown) {
  const n = num(v);
  return Number.isFinite(n) ? `${formatNumber(n, 1)} ms` : "—";
}
