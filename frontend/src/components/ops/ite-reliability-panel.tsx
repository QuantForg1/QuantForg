"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { LazyBarChart } from "@/components/charts/lazy";
import { iteReliabilityApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";

export function IteReliabilityPanel() {
  const qc = useQueryClient();
  const [timelineQ, setTimelineQ] = useState("");
  const [exportPreview, setExportPreview] = useState("");

  const dash = useQuery({
    queryKey: ["ite-rel-dash"],
    queryFn: iteReliabilityApi.dashboard,
    retry: false,
    refetchInterval: 15_000,
  });
  const timeline = useQuery({
    queryKey: ["ite-rel-timeline", timelineQ],
    queryFn: () =>
      iteReliabilityApi.timeline(
        timelineQ ? { q: timelineQ, limit: "50" } : { limit: "50" },
      ),
    retry: false,
  });

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["ite-rel-dash"] });
    void qc.invalidateQueries({ queryKey: ["ite-rel-timeline"] });
  };

  const tickMut = useMutation({
    mutationFn: () =>
      iteReliabilityApi.tick({
        gateway_available: true,
        mt5_connected: true,
        cloudflare_tunnel_up: true,
        railway_api_up: true,
        supabase_up: true,
        gateway_latency_ms: 40,
        database_latency_ms: 12,
        oms_latency_ms: 25,
        execution_latency_ms: 30,
        decision_latency_ms: 8,
        pme_latency_ms: 10,
      }),
    onSuccess: invalidate,
  });
  const chaosMut = useMutation({
    mutationFn: (failure: string) => iteReliabilityApi.chaosInject(failure),
    onSuccess: invalidate,
  });
  const clearChaosMut = useMutation({
    mutationFn: () => iteReliabilityApi.chaosClear(),
    onSuccess: invalidate,
  });
  const recoverMut = useMutation({
    mutationFn: (kind: "gateway" | "mt5") =>
      kind === "gateway"
        ? iteReliabilityApi.recoverGateway()
        : iteReliabilityApi.recoverMt5(),
    onSuccess: invalidate,
  });
  const exportMut = useMutation({
    mutationFn: (fmt: "json" | "csv") => iteReliabilityApi.timelineExport(fmt),
    onSuccess: (data) => setExportPreview(str(asRecord(data).content).slice(0, 400)),
  });

  if (dash.isLoading) return <DeskSkeleton rows={3} />;
  if (dash.isError) {
    return (
      <DeskError message="Reliability dashboard unavailable (OWNER/ADMIN · /ite/reliability/*)." />
    );
  }

  const d = asRecord(dash.data);
  const health = asRecord(d.health);
  const metrics = asRecord(d.metrics);
  const series = asList(d.latency_series).map(asRecord);
  const incidents = asList(d.active_incidents).map(asRecord);
  const recovery = asList(d.recovery_events).map(asRecord);
  const events = asList(asRecord(timeline.data).events).map(asRecord);
  const chart = series.slice(-12).map((s) => ({
    label: str(s.t).slice(11, 19) || "t",
    value: num(s.gateway, 0),
  }));

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">
            Production Reliability & Observability
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <div className="text-xs text-muted-foreground">Health score</div>
              <div className="text-xl font-semibold">{str(health.health_score, "—")}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Degraded</div>
              <Badge tone={health.degraded ? "danger" : "neutral"}>
                {health.degraded ? "YES" : "NO"}
              </Badge>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Open incidents</div>
              <div className="font-medium">{str(asRecord(d.errors).open_incidents, "0")}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Fill / reject</div>
              <div className="text-sm">
                {str(metrics.fill_rate_pct)}% / {str(metrics.reject_rate_pct)}%
              </div>
            </div>
          </div>

          {chart.length > 0 && (
            <div>
              <div className="mb-2 text-xs text-muted-foreground">Gateway latency (live)</div>
              <LazyBarChart data={chart} />
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => tickMut.mutate()} disabled={tickMut.isPending}>
              Run health tick
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => chaosMut.mutate("gateway_offline")}
            >
              Chaos: gateway
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => chaosMut.mutate("mt5_offline")}
            >
              Chaos: MT5
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => chaosMut.mutate("high_latency")}
            >
              Chaos: latency
            </Button>
            <Button size="sm" variant="secondary" onClick={() => clearChaosMut.mutate()}>
              Clear chaos
            </Button>
            <Button size="sm" variant="ghost" onClick={() => recoverMut.mutate("gateway")}>
              Recover gateway
            </Button>
            <Button size="sm" variant="ghost" onClick={() => recoverMut.mutate("mt5")}>
              Recover MT5
            </Button>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <div className="mb-2 text-sm font-medium">Active incidents</div>
              {incidents.length === 0 && (
                <p className="text-sm text-muted-foreground">None</p>
              )}
              {incidents.map((i) => (
                <div key={str(i.id)} className="mb-1 rounded border px-2 py-1 text-sm">
                  <Badge tone="neutral">{str(i.severity)}</Badge> {str(i.title)}
                </div>
              ))}
            </div>
            <div>
              <div className="mb-2 text-sm font-medium">Recovery events</div>
              {recovery.length === 0 && (
                <p className="text-sm text-muted-foreground">None yet</p>
              )}
              {recovery.slice(-5).map((e) => (
                <div key={str(e.id)} className="mb-1 text-sm">
                  {str(e.action)} · {e.success ? "ok" : "fail"}
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Audit timeline</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <input
              className="rounded border bg-background px-2 py-1 text-sm"
              placeholder="Search…"
              value={timelineQ}
              onChange={(e) => setTimelineQ(e.target.value)}
            />
            <Button size="sm" variant="outline" onClick={() => exportMut.mutate("json")}>
              Export JSON
            </Button>
            <Button size="sm" variant="outline" onClick={() => exportMut.mutate("csv")}>
              Export CSV
            </Button>
          </div>
          <div className="max-h-48 space-y-1 overflow-auto text-xs">
            {events.map((e) => (
              <div key={str(e.id)} className="border-b py-1">
                <span className="text-muted-foreground">{str(e.timestamp).slice(11, 19)}</span>{" "}
                [{str(e.category)}] {str(e.action)} — {str(e.detail)}
              </div>
            ))}
          </div>
          {exportPreview && (
            <pre className="max-h-32 overflow-auto rounded bg-muted p-2 text-[10px]">
              {exportPreview}
            </pre>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
