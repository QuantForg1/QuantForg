"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { WeltradeGatewayStatus } from "@/components/desk/weltrade-gateway-status";
import { gatewayManagerApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";

function toneFor(status: string): "success" | "warning" | "danger" | "neutral" {
  const s = status.toLowerCase();
  if (s === "online") return "success";
  if (s === "degraded" || s === "draining" || s === "unknown") return "warning";
  if (s === "offline") return "danger";
  return "neutral";
}

export default function CloudOpsPage() {
  const dashQ = useQuery({
    queryKey: ["gateway-manager-dashboard"],
    queryFn: gatewayManagerApi.dashboard,
    retry: false,
  });

  const refresh = useMutation({
    mutationFn: gatewayManagerApi.refreshHa,
    onSuccess: async () => {
      toast.success("HA refresh complete");
      await dashQ.refetch();
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "HA refresh failed"),
  });

  const data = asRecord(dashQ.data);
  const health = asRecord(data.health);
  const gateways = asList(data.registered_gateways).map(asRecord);
  const latency = asList(data.latency).map(asRecord);
  const heartbeats = asList(data.heartbeat).map(asRecord);
  const failures = asList(data.recent_failures).map(asRecord);
  const brokerMap = asRecord(data.broker_mapping);

  return (
    <div>
      <PageHeader
        title="Cloud Operations"
        description="Gateway Manager — registry, health, routing, and HA for Windows MT5 gateways."
        actions={
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={refresh.isPending}
              onClick={() => refresh.mutate()}
            >
              Refresh HA
            </Button>
            <Button size="sm" variant="secondary" onClick={() => dashQ.refetch()}>
              Refresh
            </Button>
          </div>
        }
      />

      {dashQ.isLoading ? (
        <DeskSkeleton rows={6} />
      ) : dashQ.isError ? (
        <DeskError
          message="Cloud operations unavailable."
          onRetry={() => dashQ.refetch()}
        />
      ) : (
        <div className="space-y-4">
          <WeltradeGatewayStatus />
          <p className="text-xs text-[var(--fg-subtle)]">{str(data.notes)}</p>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Registered"
              value={String(gateways.length)}
              hint={`cloud ${str(data.cloud_version) || "1.0.0"}`}
            />
            <StatCard label="Online" value={String(num(health.online, 0))} />
            <StatCard
              label="Offline / degraded"
              value={`${num(health.offline, 0)} / ${num(health.degraded, 0)}`}
            />
            <StatCard
              label="Connected users"
              value={String(num(data.connected_users, 0))}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Registered gateways</CardTitle>
            </CardHeader>
            <CardContent>
              <DeskTable
                columns={[
                  "ID",
                  "Host",
                  "Broker",
                  "Region",
                  "Status",
                  "Version",
                  "Latency",
                  "Heartbeat",
                  "Users",
                ]}
                rows={gateways.map((g) => {
                  const metrics = asRecord(g.metrics);
                  return [
                    str(g.gateway_id),
                    str(g.hostname),
                    str(g.broker),
                    str(g.region),
                    <Badge key="s" tone={toneFor(str(g.status))}>
                      {str(g.status)}
                    </Badge>,
                    str(g.version),
                    g.latency_ms == null
                      ? "—"
                      : `${formatNumber(num(g.latency_ms, 0), 1)} ms`,
                    str(g.heartbeat) || "—",
                    String(num(metrics.connected_users, 0)),
                  ];
                })}
              />
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Broker mapping</CardTitle>
              </CardHeader>
              <CardContent>
                <DeskTable
                  columns={["Broker", "Gateways"]}
                  rows={Object.entries(brokerMap).map(([broker, ids]) => [
                    broker,
                    asList(ids).map(String).join(", ") || "—",
                  ])}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Latency / heartbeat</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <DeskTable
                  columns={["Gateway", "Latency"]}
                  rows={latency.map((r) => [
                    str(r.hostname) || str(r.gateway_id),
                    r.latency_ms == null
                      ? "—"
                      : `${formatNumber(num(r.latency_ms, 0), 1)} ms`,
                  ])}
                />
                <DeskTable
                  columns={["Gateway", "Status", "Last heartbeat"]}
                  rows={heartbeats.map((r) => [
                    str(r.gateway_id),
                    <Badge key="h" tone={toneFor(str(r.status))}>
                      {str(r.status)}
                    </Badge>,
                    str(r.heartbeat) || "—",
                  ])}
                />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Recent failures</CardTitle>
            </CardHeader>
            <CardContent>
              {failures.length === 0 ? (
                <p className="text-sm text-[var(--fg-subtle)]">No failures recorded.</p>
              ) : (
                <DeskTable
                  columns={["When", "Gateway", "Reason", "Detail"]}
                  rows={failures.slice(0, 20).map((f) => [
                    str(f.at),
                    str(f.gateway_id),
                    str(f.reason),
                    str(f.detail) || "—",
                  ])}
                />
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
