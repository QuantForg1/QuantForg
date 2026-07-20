"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { executionIntelligenceApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber, formatPct } from "@/lib/utils";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";

export default function ExecutionIntelPage() {
  const [requestId, setRequestId] = useState(`obs-${Date.now()}`);
  const [symbol, setSymbol] = useState(TRADING_SYMBOL);
  const [state, setState] = useState("Validated");

  const dashQ = useQuery({
    queryKey: ["execution-intelligence-dashboard"],
    queryFn: executionIntelligenceApi.dashboard,
    retry: false,
  });

  const observe = useMutation({
    mutationFn: executionIntelligenceApi.observe,
    onSuccess: async () => {
      toast.success("Lifecycle observed");
      await dashQ.refetch();
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Observe failed"),
  });

  const checklist = useMutation({
    mutationFn: executionIntelligenceApi.checklist,
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Checklist failed"),
  });

  const data = asRecord(dashQ.data);
  const analytics = asRecord(asRecord(data.analytics).metrics);
  const analyticsStatus = str(asRecord(data.analytics).status);
  const checklistData = asRecord(checklist.data ?? data.checklist);
  const broker = asRecord(data.broker);
  const lifecycle = asList(asRecord(data.lifecycle).items).map(asRecord);
  const timeline = asList(data.timeline).map(asRecord);
  const recent = asList(data.recent_orders).map(asRecord);
  const riskDecisions = asList(data.risk_decisions).map(asRecord);
  const postTrade = asList(asRecord(data.post_trade).items).map(asRecord);
  const checklistItems = asList(checklistData.items).map(asRecord);

  return (
    <div>
      <PageHeader
        title="Execution Intelligence"
        description="Trade lifecycle, pre-trade checklist, analytics, and broker diagnostics — never enables live trading."
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
          message="Execution intelligence unavailable."
          onRetry={() => dashQ.refetch()}
        />
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge tone={data.execution_enabled ? "danger" : "success"}>
              EXECUTION_ENABLED={String(Boolean(data.execution_enabled))}
            </Badge>
            <Badge tone="neutral">autonomous={String(Boolean(data.autonomous_trading))}</Badge>
            <span className="text-[var(--fg-subtle)]">
              {str(data.execution_enabled_note)}
            </span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Fill rate"
              value={
                analytics.fill_rate == null
                  ? "n/a"
                  : formatPct(num(analytics.fill_rate, 0))
              }
              hint={analyticsStatus === "available" ? "From attempts" : "Unavailable"}
            />
            <StatCard
              label="Reject rate"
              value={
                analytics.reject_rate == null
                  ? "n/a"
                  : formatPct(num(analytics.reject_rate, 0))
              }
            />
            <StatCard
              label="Avg latency (ms)"
              value={
                analytics.order_latency_ms_avg == null
                  ? "n/a"
                  : formatNumber(num(analytics.order_latency_ms_avg, 0), 2)
              }
              hint={str(analytics.order_latency_reason) || undefined}
            />
            <StatCard
              label="Avg slippage"
              value={
                analytics.average_slippage == null
                  ? "n/a"
                  : formatNumber(num(analytics.average_slippage, 0), 5)
              }
              hint={str(analytics.average_slippage_reason) || undefined}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Pre-trade checklist</CardTitle>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => checklist.mutate({})}
                >
                  Re-run
                </Button>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex gap-2">
                  <Badge
                    tone={checklistData.ready_for_execution ? "success" : "warning"}
                  >
                    {checklistData.ready_for_execution ? "ready" : "not ready"}
                  </Badge>
                  {checklistData.blocked ? <Badge tone="danger">blocked</Badge> : null}
                </div>
                <ul className="space-y-2">
                  {checklistItems.map((item) => (
                    <li
                      key={str(item.key)}
                      className="flex items-start justify-between gap-2 rounded-md border border-[var(--border)] px-3 py-2 text-xs"
                    >
                      <div>
                        <p className="font-medium text-[var(--fg)]">{str(item.key)}</p>
                        {item.reason ? (
                          <p className="text-[var(--fg-subtle)]">{str(item.reason)}</p>
                        ) : null}
                      </div>
                      <Badge
                        tone={
                          item.status === "pass"
                            ? "success"
                            : item.status === "fail"
                              ? "danger"
                              : "warning"
                        }
                      >
                        {str(item.status)}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Broker diagnostics</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p>
                  Connection:{" "}
                  <Badge
                    tone={
                      asRecord(broker.connection).connected ? "success" : "warning"
                    }
                  >
                    {str(asRecord(broker.connection).status) ||
                      String(asRecord(broker.connection).connected)}
                  </Badge>
                </p>
                <p className="text-xs text-[var(--fg-muted)]">
                  Heartbeat:{" "}
                  {str(asRecord(broker.heartbeat).last_heartbeat_at) || "unavailable"}
                </p>
                <p className="text-xs text-[var(--fg-muted)]">
                  Gateway latency:{" "}
                  {broker.gateway_latency_ms == null
                    ? "n/a"
                    : `${formatNumber(num(broker.gateway_latency_ms, 0), 1)} ms`}
                </p>
                <p className="text-xs text-[var(--fg-muted)]">
                  Last disconnect:{" "}
                  {str(broker.last_disconnect_reason) || "unavailable"}
                </p>
                <p className="text-xs text-[var(--fg-subtle)]">
                  Reconnect events: {str(broker.reconnect_count)} ·{" "}
                  {str(broker.reconnect_history_status)}
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Lifecycle timeline</CardTitle>
            </CardHeader>
            <CardContent>
              {timeline.length === 0 ? (
                <p className="text-sm text-[var(--fg-subtle)]">
                  No lifecycle records yet. Use observe or run execution check/submit
                  (attempts are ingested automatically).
                </p>
              ) : (
                <ul className="space-y-2">
                  {timeline.map((row) => (
                    <motion.li
                      key={str(row.lifecycle_id)}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="rounded-lg border border-[var(--border)] px-3 py-2 text-xs"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium">
                          {str(row.symbol)} · {str(row.request_id)}
                        </span>
                        <Badge tone="accent">{str(row.state)}</Badge>
                      </div>
                      <p className="mt-1 text-[var(--fg-subtle)]">
                        history {asList(row.history).length} · updated{" "}
                        {str(row.updated_at)}
                      </p>
                    </motion.li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Recent orders / attempts</CardTitle>
              </CardHeader>
              <CardContent>
                <DeskTable
                  columns={["Request", "Symbol", "Outcome", "Retcode"]}
                  rows={recent.slice(0, 10).map((r) => [
                    str(r.request_id),
                    str(r.symbol),
                    str(r.outcome),
                    str(r.retcode),
                  ])}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Risk / safety decisions</CardTitle>
              </CardHeader>
              <CardContent>
                <DeskTable
                  columns={["Request", "Decision", "Symbol"]}
                  rows={riskDecisions.slice(0, 10).map((r) => [
                    str(r.request_id),
                    str(r.decision),
                    str(r.symbol),
                  ])}
                />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Post-trade analysis</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {postTrade.length === 0 ? (
                <p className="text-sm text-[var(--fg-subtle)]">
                  {str(asRecord(data.post_trade).reason) ||
                    "No completed trades for post-trade analysis"}
                </p>
              ) : (
                postTrade.slice(0, 8).map((t, i) => {
                  const ex = asRecord(t.explanation);
                  return (
                    <div
                      key={i}
                      className="rounded-lg border border-[var(--border)] p-3 text-xs"
                    >
                      <div className="flex justify-between gap-2">
                        <span className="font-medium">
                          {str(t.symbol)} · {str(t.side)}
                        </span>
                        <Badge tone="neutral">
                          pnl {formatNumber(num(t.pnl_contribution, 0), 2)}
                        </Badge>
                      </div>
                      <p className="mt-1 text-[var(--fg-muted)]">{str(ex.reason)}</p>
                      <p className="text-[var(--fg-subtle)]">
                        conf {formatNumber(num(ex.confidence, 0) * 100, 0)}% ·{" "}
                        {str(ex.data_source)}
                      </p>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Observe lifecycle event</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-4">
              <div className="space-y-1">
                <Label>Request ID</Label>
                <Input value={requestId} onChange={(e) => setRequestId(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>Symbol</Label>
                <Input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
              </div>
              <div className="space-y-1">
                <Label>State</Label>
                <Input value={state} onChange={(e) => setState(e.target.value)} />
              </div>
              <div className="flex items-end">
                <Button
                  className="w-full"
                  disabled={observe.isPending}
                  onClick={() =>
                    observe.mutate({
                      request_id: requestId,
                      symbol,
                      side: "buy",
                      order_type: "market",
                      volume: "0.01",
                      state,
                      reason: "manual observe from UI",
                      source: "execution_intel_ui",
                      force: true,
                    })
                  }
                >
                  Record
                </Button>
              </div>
              <p className="sm:col-span-4 text-xs text-[var(--fg-subtle)]">
                Active lifecycles: {lifecycle.filter((l) => !l.archived).length} ·
                Archived: {lifecycle.filter((l) => l.archived).length}
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
