"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { LazyBarChart } from "@/components/charts/lazy";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { PageMotion } from "@/components/desk/motion";
import { mt5Api, opsApi, platformApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";
import { env } from "@/lib/env";
import { useRealtimeContext } from "@/providers/realtime-provider";
import { listMonitoredErrors } from "@/lib/observability/error-monitor";
import { listAuditEvents } from "@/lib/observability/audit";
import { describeFlags } from "@/lib/platform/flags";
import { getBetaState } from "@/lib/platform/beta";

function toneFor(status: string): "success" | "warning" | "danger" | "accent" | "neutral" {
  const s = status.toLowerCase();
  if (s === "healthy" || s === "ok" || s === "up" || s === "connected" || s === "alive")
    return "success";
  if (s === "degraded" || s === "polling") return "accent";
  if (s === "unhealthy" || s === "down" || s === "error" || s === "disconnected") return "danger";
  if (s === "unknown") return "warning";
  return "neutral";
}

export default function OpsPage() {
  const realtime = useRealtimeContext();
  const [clientErrors, setClientErrors] = useState(() => listMonitoredErrors());
  const [clientAudit, setClientAudit] = useState(() => listAuditEvents());
  const flags = describeFlags();
  const beta = getBetaState();

  useEffect(() => {
    const t = setInterval(() => {
      setClientErrors(listMonitoredErrors());
      setClientAudit(listAuditEvents());
    }, 5000);
    return () => clearInterval(t);
  }, []);

  const health = useQuery({
    queryKey: ["health"],
    queryFn: platformApi.health,
    retry: false,
    refetchInterval: 30_000,
  });
  const healthLive = useQuery({
    queryKey: ["health-live"],
    queryFn: platformApi.healthLive,
    retry: false,
    refetchInterval: 30_000,
  });
  const versionQ = useQuery({
    queryKey: ["platform-version"],
    queryFn: platformApi.version,
    retry: false,
  });
  const dashboard = useQuery({
    queryKey: ["ops-dashboard"],
    queryFn: opsApi.dashboard,
    retry: false,
    refetchInterval: 30_000,
  });
  const metrics = useQuery({
    queryKey: ["ops-metrics"],
    queryFn: opsApi.metrics,
    retry: false,
  });
  const alerts = useQuery({
    queryKey: ["ops-alerts"],
    queryFn: opsApi.alerts,
    retry: false,
  });
  const serverAudit = useQuery({
    queryKey: ["ops-audit"],
    queryFn: opsApi.audit,
    retry: false,
  });
  const mt5 = useQuery({
    queryKey: ["mt5-status"],
    queryFn: mt5Api.status,
    retry: false,
    refetchInterval: 30_000,
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
  const redis = findDep("redis") || findComp("redis");
  const queue = findComp("queue") || findDep("queue") || findDep("celery") || findDep("worker");
  const jobs = findComp("jobs") || findComp("worker") || findDep("jobs");
  const api = findComp("api") || { status: health.data?.status, latency_ms: null };
  const mt5Comp = findComp("mt5") || findDep("mt5");
  const realtimeComp = findComp("realtime") || findDep("realtime");

  const alertRows = asList(alerts.data?.items ?? alerts.data).map(asRecord);
  const serverAuditRows = asList(serverAudit.data?.items ?? serverAudit.data).map(asRecord);
  const ver = asRecord(versionQ.data);

  const deployments = [
    {
      target: "Frontend",
      version: env.buildVersion,
      environment: env.appEnv,
      note: "NEXT_PUBLIC_BUILD_VERSION / Vercel SHA",
    },
    {
      target: "API health",
      version: str(health.data?.version, "—"),
      environment: str(health.data?.environment, "—"),
      note: "GET /health",
    },
    {
      target: "API version",
      version: str(ver.version ?? ver.git_sha ?? ver.commit, "—"),
      environment: str(ver.environment ?? ver.env, "—"),
      note: "GET /api/v1/version",
    },
  ];

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
              label="API health"
              value={str(dashboard.data?.overall ?? health.data?.status, "—")}
              hint={str(healthLive.data?.status ?? health.data?.status, "")}
            />
            <StatCard
              label="Realtime"
              value={realtime.status.connected ? realtime.status.transport : "offline"}
              hint={
                realtime.status.latencyMs != null
                  ? `${formatNumber(realtime.status.latencyMs, 0)} ms`
                  : str(asRecord(realtimeComp).status, "")
              }
            />
            <StatCard
              label="Broker / MT5"
              value={
                mt5.data?.connected
                  ? "connected"
                  : str(asRecord(mt5Comp).status, mt5.isError ? "error" : "disconnected")
              }
              hint={lat(mt5.data?.latency_ms ?? asRecord(mt5Comp).latency_ms)}
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
              label="Queue / jobs"
              value={str(
                asRecord(queue).status ?? asRecord(jobs).status,
                str(dashboard.data?.execution_enabled) === "true" ? "enabled" : "—",
              )}
              hint={lat(asRecord(queue).latency_ms ?? asRecord(jobs).latency_ms)}
            />
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Latency"
              value={
                Number.isFinite(num(m.request_latency_ms_avg))
                  ? `${formatNumber(num(m.request_latency_ms_avg), 1)} ms`
                  : lat(asRecord(api).latency_ms)
              }
            />
            <StatCard label="Version" value={env.buildVersion} hint={str(health.data?.version, "")} />
            <StatCard label="Environment" value={env.appEnv} hint={str(health.data?.environment, "")} />
            <StatCard
              label="Beta / modes"
              value={beta.betaMode ? (beta.unlocked ? "beta unlocked" : "invite gate") : "open"}
              hint={[
                beta.maintenanceMode ? "maintenance" : null,
                beta.readOnlyMode ? "read-only" : null,
              ]
                .filter(Boolean)
                .join(" · ") || "normal"}
            />
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-2">
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

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
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
                  <DeskError
                    message="Metrics endpoint restricted to privileged operators."
                    onRetry={() => metrics.refetch()}
                  />
                ) : (
                  <DeskTable
                    columns={["Metric", "Value"]}
                    rows={[
                      ["Request latency avg", lat(m.request_latency_ms_avg)],
                      [
                        "Error rate",
                        Number.isFinite(num(m.error_rate))
                          ? formatNumber(num(m.error_rate), 4)
                          : "—",
                      ],
                      ["Throughput / min", str(m.throughput_per_minute, "—")],
                      [
                        "Cache hit ratio",
                        Number.isFinite(num(m.cache_hit_ratio))
                          ? formatNumber(num(m.cache_hit_ratio), 3)
                          : "—",
                      ],
                      ["Requests", str(m.request_count, "—")],
                      ["Errors", str(m.error_count, "—")],
                    ].map(([a, b]) => [a, b])}
                  />
                )}
              </CardContent>
            </Card>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Feature flags</CardTitle>
              </CardHeader>
              <CardContent>
                <DeskTable
                  columns={["Flag", "State", "Source"]}
                  rows={flags.map((f) => [
                    f.key,
                    <Badge key="e" tone={f.enabled ? "success" : "neutral"}>
                      {f.enabled ? "on" : "off"}
                    </Badge>,
                    f.source,
                  ])}
                />
                <p className="mt-2 text-xs text-[var(--fg-muted)]">
                  Toggle via NEXT_PUBLIC_FF_* or localStorage overrides (qf.ff.overrides.v1) — no
                  redeploy required for overrides.
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Recent deployments</CardTitle>
              </CardHeader>
              <CardContent>
                <DeskTable
                  columns={["Target", "Version", "Environment", "Source"]}
                  rows={deployments.map((d) => [d.target, d.version, d.environment, d.note])}
                />
              </CardContent>
            </Card>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Recent errors</CardTitle>
              </CardHeader>
              <CardContent>
                {clientErrors.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">No client-captured errors yet.</p>
                ) : (
                  <DeskTable
                    columns={["Kind", "Message", "Route", "Request"]}
                    rows={clientErrors.slice(0, 12).map((e) => [
                      e.kind,
                      e.message.slice(0, 60),
                      e.route,
                      e.request_id.slice(0, 12),
                    ])}
                  />
                )}
                {alerts.isError ? (
                  <p className="mt-2 text-xs text-[var(--fg-muted)]">
                    Server alerts require owner/admin.
                  </p>
                ) : alertRows.length > 0 ? (
                  <div className="mt-3">
                    <p className="mb-1 text-xs font-medium text-[var(--fg-muted)]">Server alerts</p>
                    <DeskTable
                      columns={["Severity", "Message"]}
                      rows={alertRows.slice(0, 8).map((a) => [
                        str(a.severity ?? a.level, "info"),
                        str(a.message ?? a.summary).slice(0, 80),
                      ])}
                    />
                  </div>
                ) : null}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Recent audit</CardTitle>
              </CardHeader>
              <CardContent>
                {clientAudit.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">No client audit events yet.</p>
                ) : (
                  <DeskTable
                    columns={["Action", "Outcome", "Summary"]}
                    rows={clientAudit.slice(0, 12).map((a) => [
                      a.action,
                      <Badge
                        key="o"
                        tone={
                          a.outcome === "success"
                            ? "success"
                            : a.outcome === "failure"
                              ? "danger"
                              : "neutral"
                        }
                      >
                        {a.outcome}
                      </Badge>,
                      a.summary.slice(0, 60),
                    ])}
                  />
                )}
                {serverAudit.isError ? (
                  <p className="mt-2 text-xs text-[var(--fg-muted)]">
                    Server audit requires owner/admin.
                  </p>
                ) : serverAuditRows.length > 0 ? (
                  <div className="mt-3">
                    <p className="mb-1 text-xs font-medium text-[var(--fg-muted)]">Server audit</p>
                    <DeskTable
                      columns={["Action", "Detail"]}
                      rows={serverAuditRows.slice(0, 8).map((a) => [
                        str(a.action ?? a.event_type, "—"),
                        str(a.summary ?? a.message ?? a.detail).slice(0, 80),
                      ])}
                    />
                  </div>
                ) : null}
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
