"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { brokerConnectivityApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";

function yesNo(v: unknown): string {
  return v ? "yes" : "no";
}

export default function BrokerConnectivityPage() {
  const [platform, setPlatform] = useState("mt5");

  const dashQ = useQuery({
    queryKey: ["broker-connectivity-dashboard"],
    queryFn: brokerConnectivityApi.dashboard,
    retry: false,
  });

  const probe = useMutation({
    mutationFn: (cap: string) =>
      brokerConnectivityApi.invoke({ platform, capability: cap }),
    onSuccess: (data) => {
      const status = str(asRecord(data).status);
      toast.message(`${platform} · ${status}`);
      void dashQ.refetch();
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Invoke failed"),
  });

  const data = asRecord(dashQ.data);
  const catalog = asList(data.catalog).map(asRecord);
  const matrix = asList(data.matrix).map(asRecord);
  const diagnostics = asRecord(data.diagnostics);
  const adapters = asList(diagnostics.adapters).map(asRecord);
  const mt5Diag =
    adapters.find((a) => str(a.platform) === "mt5") ?? asRecord({});
  const reconnect = asList(diagnostics.reconnect_manager).map(asRecord);
  const failures = asList(asRecord(mt5Diag).failures).map(asRecord);

  return (
    <div>
      <PageHeader
        title="Broker Connectivity"
        description="Adapter framework, capability matrix, and live MT5 diagnostics — no simulated venues."
        actions={
          <Button size="sm" variant="secondary" onClick={() => dashQ.refetch()}>
            Refresh
          </Button>
        }
      />

      {dashQ.isLoading ? (
        <DeskSkeleton rows={6} />
      ) : dashQ.isError ? (
        <DeskError
          message="Broker connectivity unavailable."
          onRetry={() => dashQ.refetch()}
        />
      ) : (
        <div className="space-y-4">
          <p className="text-xs text-[var(--fg-subtle)]">{str(data.notes)}</p>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Adapters"
              value={String(catalog.length)}
              hint={`${catalog.filter((c) => c.implemented).length} implemented`}
            />
            <StatCard
              label="MT5 connected"
              value={mt5Diag.connected ? "yes" : "no"}
              hint={str(asRecord(asRecord(mt5Diag.health).data).server) || undefined}
            />
            <StatCard
              label="Latency (ms)"
              value={
                mt5Diag.latency_ms == null
                  ? "n/a"
                  : formatNumber(num(mt5Diag.latency_ms, 0), 2)
              }
            />
            <StatCard
              label="Failures (MT5)"
              value={String(failures.length)}
              hint="Recent structured failures"
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Capability matrix</CardTitle>
            </CardHeader>
            <CardContent>
              <DeskTable
                columns={[
                  "Platform",
                  "Live",
                  "Orders",
                  "Margin",
                  "Leverage",
                  "Netting",
                  "Hedging",
                  "Market data",
                  "History",
                  "Streaming",
                ]}
                rows={matrix.map((row) => [
                  <span key="n" className="font-medium">
                    {str(row.name)}
                    <span className="ml-2 text-[var(--fg-subtle)]">
                      ({str(row.platform)})
                    </span>
                  </span>,
                  <Badge
                    key="i"
                    tone={row.implemented ? "success" : "neutral"}
                  >
                    {row.implemented ? "implemented" : "unsupported"}
                  </Badge>,
                  asList(row.order_types).map(String).join(", ") || "—",
                  yesNo(row.margin),
                  yesNo(row.leverage),
                  yesNo(row.netting),
                  yesNo(row.hedging),
                  yesNo(row.market_data),
                  yesNo(row.history),
                  yesNo(row.streaming),
                ])}
              />
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Adapter catalog</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {catalog.map((c) => (
                  <button
                    key={str(c.platform)}
                    type="button"
                    className={`flex w-full items-center justify-between rounded border px-3 py-2 text-left text-sm ${
                      platform === str(c.platform)
                        ? "border-[var(--accent)] bg-[var(--bg-elevated)]"
                        : "border-[var(--border)]"
                    }`}
                    onClick={() => setPlatform(str(c.platform))}
                  >
                    <span>
                      {str(c.name)}{" "}
                      <span className="text-[var(--fg-subtle)]">
                        ({str(c.platform)})
                      </span>
                    </span>
                    <Badge tone={c.implemented ? "success" : "neutral"}>
                      {c.implemented ? "live" : "stub"}
                    </Badge>
                  </button>
                ))}
                <div className="flex flex-wrap gap-2 pt-2">
                  {["health", "heartbeat", "capabilities", "balances", "trading"].map(
                    (cap) => (
                      <Button
                        key={cap}
                        size="sm"
                        variant="secondary"
                        disabled={probe.isPending}
                        onClick={() => probe.mutate(cap)}
                      >
                        {cap}
                      </Button>
                    ),
                  )}
                </div>
                {probe.data ? (
                  <pre className="mt-2 max-h-48 overflow-auto rounded bg-[var(--bg-elevated)] p-2 text-xs">
                    {JSON.stringify(probe.data, null, 2)}
                  </pre>
                ) : null}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Diagnostics</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div>
                  <div className="mb-1 text-xs text-[var(--fg-subtle)]">
                    Capability checks (MT5)
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(
                      asRecord(asRecord(mt5Diag).capability_checks),
                    ).map(([k, v]) => (
                      <Badge key={k} tone={v ? "success" : "neutral"}>
                        {k}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="mb-1 text-xs text-[var(--fg-subtle)]">
                    Reconnect manager
                  </div>
                  {reconnect.length === 0 ? (
                    <p className="text-[var(--fg-subtle)]">No reconnect state.</p>
                  ) : (
                    <DeskTable
                      columns={["Connection", "Attempts", "Last"]}
                      rows={reconnect.map((r) => [
                        str(r.connection_id).slice(0, 8),
                        String(r.attempts ?? 0),
                        str(r.last_attempt_at) || "—",
                      ])}
                    />
                  )}
                </div>
                <div>
                  <div className="mb-1 text-xs text-[var(--fg-subtle)]">
                    Recent MT5 failures
                  </div>
                  {failures.length === 0 ? (
                    <p className="text-[var(--fg-subtle)]">None recorded.</p>
                  ) : (
                    <ul className="space-y-1 text-xs">
                      {failures.slice(-8).map((f, i) => (
                        <li key={`${str(f.at)}-${i}`}>
                          {str(f.capability)} · {str(f.reason)}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
