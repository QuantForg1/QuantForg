"use client";

import dynamic from "next/dynamic";
import { useState, useTransition } from "react";
import { useNocCommandCenter } from "@/hooks/use-noc-command-center";
import { useAuth } from "@/providers/auth-provider";
import {
  canAccessIteOps,
  iteOpsAccessDeniedMessage,
} from "@/lib/auth/ite-ops-access";
import { asList, asRecord, str } from "@/lib/desk";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { cn } from "@/lib/utils";
import {
  fmt,
  HealthCard,
  MetricBar,
  NocPanel,
  NocRow,
  pipelineTone,
} from "@/components/ops/noc/noc-primitives";

function filterValidationHistory(history: unknown[], filter: string): unknown[] {
  const q = filter.trim().toLowerCase();
  if (!q) return history;
  return history.filter((row) => {
    const r = asRecord(row);
    const blob = [
      r.validation_id,
      r.final_result,
      r.pipeline_status,
      r.result,
      r.first_blocker,
      r.reason,
      r.ai_action,
      r.symbol,
    ]
      .map((x) => String(x ?? "").toLowerCase())
      .join(" ");
    return blob.includes(q);
  });
}

const NocCopilotPanel = dynamic(
  () =>
    import("@/components/ops/noc/noc-copilot-panel").then((m) => m.NocCopilotPanel),
  { ssr: false, loading: () => <DeskSkeleton rows={6} /> },
);

function TopBar({
  header,
  version,
  healthOk,
  buildVersion,
}: {
  header: Record<string, unknown>;
  version: Record<string, unknown>;
  healthOk: boolean;
  buildVersion: string;
}) {
  const commit = str(header.commit_sha, "—");
  const envName = str(header.environment || version.environment, "—");
  const ver = str(header.version || version.version, buildVersion || "—");
  return (
    <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
      <span className="text-[13px] font-semibold tracking-tight text-[var(--fg)]">
        QuantForg Command Center
      </span>
      <Badge tone={healthOk ? "success" : "warning"}>
        {healthOk ? "LIVE" : "DEGRADED"}
      </Badge>
      <Badge tone="neutral">Env · {envName}</Badge>
      <Badge tone="neutral">Production</Badge>
      <span className="font-mono text-[11px] text-[var(--fg-muted)]">
        v{ver}
      </span>
      <span className="font-mono text-[11px] text-[var(--fg-subtle)]" title={commit}>
        SHA {commit.slice(0, 12)}
      </span>
      <span className="font-mono text-[11px] text-[var(--fg-subtle)]">
        Deploy {str(header.deployment_time, "—")}
      </span>
      <Badge
        tone={
          str(header.railway_status) === "online" ? "success" : "warning"
        }
      >
        Railway · {str(header.railway_status, "unknown")}
      </Badge>
      <span className="ml-auto text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        Observe-only · real telemetry
      </span>
    </div>
  );
}

function PipelineStrip({
  nodes,
  validationId,
}: {
  nodes: unknown[];
  validationId: string;
}) {
  return (
    <div className="overflow-x-auto">
      <div className="flex min-w-max items-stretch gap-1">
        {nodes.map((raw, idx) => {
          const n = asRecord(raw);
          const status = str(n.status, "WAITING");
          const tone = pipelineTone(status);
          return (
            <div key={`${str(n.stage)}-${idx}`} className="flex items-center gap-1">
              <div
                className={cn(
                  "min-w-[112px] border px-2 py-2 transition-colors duration-[var(--duration-os)]",
                  tone === "ok" && "border-[var(--success)] bg-[var(--success-soft)]",
                  tone === "bad" && "border-[var(--danger)] bg-[var(--danger-soft)]",
                  tone === "warn" && "border-[var(--warning)] bg-[var(--warning-soft)]",
                  !tone && "border-[var(--border)] bg-[var(--surface-2)]",
                )}
              >
                <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--fg)]">
                  {str(n.stage, "—")}
                </p>
                <p
                  className={cn(
                    "mt-1 font-mono text-[11px]",
                    tone === "ok" && "text-[var(--success)]",
                    tone === "bad" && "text-[var(--danger)]",
                    tone === "warn" && "text-[var(--warning)]",
                  )}
                >
                  {status}
                </p>
                <p className="mt-0.5 font-mono text-[10px] text-[var(--fg-subtle)]">
                  {n.latency_ms == null ? "—" : `${n.latency_ms} ms`}
                </p>
                <p
                  className="mt-0.5 max-w-[140px] truncate text-[10px] text-[var(--fg-muted)]"
                  title={str(n.reason, "")}
                >
                  {str(n.reason, "—")}
                </p>
              </div>
              {idx < nodes.length - 1 ? (
                <span className="px-0.5 font-mono text-[12px] text-[var(--fg-subtle)]">
                  ↓
                </span>
              ) : null}
            </div>
          );
        })}
      </div>
      <p className="mt-2 font-mono text-[11px] text-[var(--fg-muted)]">
        Validation ID · {validationId || "—"}
      </p>
    </div>
  );
}

export function NocCommandCenter() {
  const { user } = useAuth();
  const allowed = canAccessIteOps(user);
  const { noc, version, healthLive, copilot, buildVersion } =
    useNocCommandCenter(allowed);
  const [filter, setFilter] = useState("");
  const [pending, startTransition] = useTransition();

  const data = asRecord(noc.data);
  const header = asRecord(data.header);
  const health = asList(data.global_health);
  const pipeline = asRecord(data.pipeline);
  const nodes = asList(pipeline.nodes);
  const ai = asRecord(data.ai_engine);
  const market = asRecord(data.market_context);
  const positions = asList(data.open_positions);
  const closed = asList(data.closed_trades);
  const oms = asRecord(data.oms);
  const gateway = asRecord(data.gateway);
  const broker = asRecord(data.broker);
  const perf = asRecord(asRecord(data.performance).today);
  const events = asList(data.event_stream);
  const alerts = asList(data.alerts);
  const history = asList(data.validation_history);
  const metrics = asRecord(data.system_metrics);

  const filteredHistory = filterValidationHistory(history, filter);

  if (!allowed) {
    return (
      <DeskError message={iteOpsAccessDeniedMessage(user, undefined, "NOC Command Center")} />
    );
  }

  if (noc.isLoading && !noc.data) {
    return <DeskSkeleton rows={12} />;
  }

  if (noc.error && !noc.data) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(user, noc.error, "NOC Command Center")}
      />
    );
  }

  const healthOk = str(asRecord(healthLive.data).status, "") === "ok";
  const reasons = asList(ai.reasons).map(String);

  return (
    <div className="space-y-4 lg:grid lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-4 lg:space-y-0">
      <div className="space-y-4">
        <TopBar
          header={header}
          version={asRecord(version.data)}
          healthOk={healthOk}
          buildVersion={buildVersion}
        />

        <NocPanel title="Global System Health">
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {health.map((row) => {
              const c = asRecord(row);
              return (
                <HealthCard
                  key={str(c.key || c.label)}
                  label={str(c.label, "—")}
                  status={str(c.status, "unknown")}
                  latencyMs={c.latency_ms}
                  heartbeat={c.last_heartbeat}
                  detail={c.detail}
                />
              );
            })}
          </div>
        </NocPanel>

        <NocPanel
          title="Live Execution Pipeline"
          action={
            <Badge tone={str(pipeline.final_result) === "ACCEPTED" ? "success" : "warning"}>
              {str(pipeline.final_result, "—")}
            </Badge>
          }
        >
          <PipelineStrip
            nodes={nodes}
            validationId={str(pipeline.validation_id, "—")}
          />
          {pipeline.first_blocker ? (
            <p className="mt-2 text-[12px] text-[var(--warning)]">
              First blocker · {str(pipeline.first_blocker)}
            </p>
          ) : null}
        </NocPanel>

        <div className="grid gap-3 lg:grid-cols-2">
          <NocPanel title="AI Engine">
            <NocRow label="Session" value={str(ai.current_session, "—")} />
            <NocRow label="Symbol" value={str(ai.symbol, "—")} />
            <NocRow
              label="Decision"
              value={str(ai.decision, "—")}
              tone={
                ["BUY", "SELL"].includes(str(ai.decision).toUpperCase())
                  ? "ok"
                  : "warn"
              }
            />
            <NocRow
              label="Quality / Threshold"
              value={`${fmt(ai.quality_score)} / ${fmt(ai.threshold)}`}
            />
            <NocRow label="Confidence" value={fmt(ai.confidence)} />
            <NocRow label="Liquidity" value={fmt(ai.liquidity)} />
            <NocRow label="Spread" value={fmt(ai.spread)} />
            <NocRow label="ATR" value={fmt(ai.atr)} />
            <NocRow label="FVG" value={fmt(ai.fvg)} />
            <NocRow label="Order Blocks" value={fmt(ai.order_blocks)} />
            <NocRow label="BOS" value={fmt(ai.bos)} />
            <NocRow label="CHOCH" value={fmt(ai.choch)} />
            {reasons.length > 0 ? (
              <ul className="mt-2 max-h-36 space-y-1 overflow-auto text-[11px] text-[var(--fg-muted)]">
                {reasons.map((r) => (
                  <li key={r}>· {r}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">No NO_TRADE reasons in snapshot.</p>
            )}
          </NocPanel>

          <NocPanel title="Market Context">
            <NocRow label="Trend" value={str(market.trend, "—")} />
            <NocRow label="Structure" value={str(market.market_structure, "—")} />
            <NocRow label="MTF Alignment" value={fmt(market.mtf_alignment)} />
            <NocRow label="Session" value={str(market.session, "—")} />
            <NocRow label="News Protection" value={fmt(market.news_protection)} />
            <NocRow label="Volatility" value={fmt(market.volatility)} />
            <NocRow label="Spread" value={fmt(market.spread)} />
            <NocRow label="ATR" value={fmt(market.atr)} />
            <NocRow label="Liquidity" value={fmt(market.liquidity)} />
            <NocRow
              label="Market Data"
              value={market.market_data_live ? "LIVE" : "—"}
              tone={market.market_data_live ? "ok" : "warn"}
            />
          </NocPanel>
        </div>

        <NocPanel title="Open Positions">
          {positions.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">No open managed positions in telemetry.</p>
          ) : (
            <DeskTable
              columns={[
                "Ticket",
                "Symbol",
                "Dir",
                "Entry",
                "Price",
                "Profit",
                "Swap",
                "Duration",
                "Risk",
                "Float P/L",
                "Broker",
              ]}
              rows={positions.map((p) => {
                const r = asRecord(p);
                return [
                  fmt(r.ticket),
                  fmt(r.symbol),
                  fmt(r.direction),
                  fmt(r.entry),
                  fmt(r.current_price),
                  fmt(r.profit),
                  fmt(r.swap),
                  fmt(r.duration),
                  fmt(r.risk),
                  fmt(r.floating_pnl),
                  fmt(r.broker),
                ];
              })}
            />
          )}
        </NocPanel>

        <NocPanel title="Recent Closed / Execution Attempts">
          {closed.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No closed-trade fields in journal telemetry (never fabricated).
            </p>
          ) : (
            <DeskTable
              columns={["Ticket", "Symbol", "Entry/Detail", "Exit/Status", "Latency", "Reason"]}
              rows={closed.slice(0, 40).map((p) => {
                const r = asRecord(p);
                return [
                  fmt(r.ticket),
                  fmt(r.symbol),
                  fmt(r.entry),
                  fmt(r.exit),
                  r.execution_latency_ms == null ? "—" : `${r.execution_latency_ms} ms`,
                  fmt(r.reason_closed),
                ];
              })}
            />
          )}
        </NocPanel>

        <div className="grid gap-3 lg:grid-cols-3">
          <NocPanel title="OMS">
            <NocRow label="Status" value={str(oms.status, "—")} />
            <NocRow label="Queue Size" value={fmt(oms.queue_size)} />
            <NocRow label="Avg Latency" value={oms.average_latency_ms == null ? "—" : `${oms.average_latency_ms} ms`} />
            <NocRow label="Retries" value={fmt(oms.retries)} />
            <NocRow label="Failures (window)" value={fmt(oms.failures_today)} />
            <NocRow
              label="Success Rate"
              value={
                oms.success_rate == null
                  ? "—"
                  : `${(Number(oms.success_rate) * 100).toFixed(1)}%`
              }
            />
          </NocPanel>
          <NocPanel title="MT5 Gateway">
            <NocRow label="Version" value={fmt(gateway.gateway_version)} />
            <NocRow label="Connection" value={str(gateway.connection, "—")} />
            <NocRow label="Ping" value={gateway.ping_ms == null ? "—" : `${gateway.ping_ms} ms`} />
            <NocRow label="Reconnects" value={fmt(gateway.reconnect_count)} />
            <NocRow label="Last Error" value={fmt(gateway.last_error)} tone={gateway.last_error ? "warn" : undefined} />
            <NocRow
              label="order_send Latency"
              value={
                gateway.order_send_latency_ms == null
                  ? "—"
                  : `${gateway.order_send_latency_ms} ms`
              }
            />
          </NocPanel>
          <NocPanel title="Broker">
            <NocRow
              label="Connected"
              value={broker.broker_connected ? "YES" : "NO"}
              tone={broker.broker_connected ? "ok" : "bad"}
            />
            <NocRow label="Account" value={fmt(broker.account)} />
            <NocRow label="Balance" value={fmt(broker.balance)} />
            <NocRow label="Equity" value={fmt(broker.equity)} />
            <NocRow label="Margin" value={fmt(broker.margin)} />
            <NocRow label="Free Margin" value={fmt(broker.free_margin)} />
            <NocRow label="Leverage" value={fmt(broker.leverage)} />
            <NocRow label="Server" value={fmt(broker.server)} />
          </NocPanel>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <NocPanel title="Performance · Today (diagnostics)">
            <div className="grid grid-cols-2 gap-x-4">
              <NocRow label="Trades" value={fmt(perf.trades)} />
              <NocRow label="Signals" value={fmt(perf.signals)} />
              <NocRow label="Rejected" value={fmt(perf.rejected)} />
              <NocRow label="Win Rate" value={fmt(perf.win_rate)} />
              <NocRow label="Profit Factor" value={fmt(perf.profit_factor)} />
              <NocRow label="Expectancy" value={fmt(perf.expectancy)} />
              <NocRow label="Avg RR" value={fmt(perf.average_rr)} />
              <NocRow label="Avg Latency" value={fmt(perf.average_latency_ms)} />
              <NocRow label="Net Profit" value={fmt(perf.net_profit)} />
              <NocRow label="Drawdown" value={fmt(perf.drawdown)} />
            </div>
            <p className="mt-2 text-[10px] text-[var(--fg-subtle)]">
              Null fields mean unavailable in live diagnostics — never mocked.
            </p>
          </NocPanel>

          <NocPanel title="System Metrics">
            <MetricBar label="CPU %" value={metrics.cpu} max={100} />
            <MetricBar label="Memory %" value={metrics.memory} max={100} />
            <MetricBar label="Gateway Latency ms" value={metrics.gateway_latency_ms} />
            <MetricBar label="OMS Latency ms" value={metrics.oms_latency_ms} />
            <MetricBar label="Broker Latency ms" value={metrics.broker_latency_ms} />
            <NocRow label="Req Latency Avg" value={fmt(metrics.request_latency_ms_avg)} />
            <NocRow label="Throughput / min" value={fmt(metrics.throughput_per_minute)} />
            <NocRow label="Error Rate" value={fmt(metrics.error_rate)} />
            <NocRow label="Executions" value={fmt(metrics.execution_count)} />
            <NocRow label="Trades Today" value={fmt(metrics.trades_today)} />
            <p className="mt-2 text-[10px] text-[var(--fg-subtle)]">
              Bars render only for real collected values — null stays empty.
            </p>
          </NocPanel>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <NocPanel title="Live Event Stream">
            <ul className="max-h-72 space-y-1 overflow-auto text-[11px]">
              {events.slice(0, 80).map((e, i) => {
                const r = asRecord(e);
                const level = str(r.level, "info");
                return (
                  <li
                    key={`${str(r.timestamp)}-${i}`}
                    className={cn(
                      "border-b border-[var(--border)]/50 py-1 font-mono",
                      level === "critical" && "text-[var(--danger)]",
                      level === "warning" && "text-[var(--warning)]",
                      level === "info" && "text-[var(--fg-muted)]",
                    )}
                  >
                    <span className="text-[var(--fg-subtle)]">{str(r.timestamp, "—").slice(11, 19)}</span>{" "}
                    {str(r.message, "—")}
                    {r.reason ? ` · ${str(r.reason)}` : ""}
                  </li>
                );
              })}
            </ul>
          </NocPanel>

          <NocPanel title="Alert Center">
            <ul className="max-h-72 space-y-2 overflow-auto text-[12px]">
              {alerts.length === 0 ? (
                <li className="text-[var(--fg-muted)]">No alerts in window.</li>
              ) : (
                alerts.slice(0, 40).map((a, i) => {
                  const r = asRecord(a);
                  const sev = str(r.severity || r.level, "info").toLowerCase();
                  return (
                    <li
                      key={str(r.id, String(i))}
                      className="border border-[var(--border)] px-2 py-1.5"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <Badge
                          tone={
                            sev === "critical"
                              ? "danger"
                              : sev === "warning"
                                ? "warning"
                                : "neutral"
                          }
                        >
                          {sev}
                        </Badge>
                        <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
                          {str(r.created_at || r.timestamp, "—").slice(0, 19)}
                        </span>
                      </div>
                      <p className="mt-1 text-[var(--fg)]">{str(r.message, "—")}</p>
                    </li>
                  );
                })
              )}
            </ul>
          </NocPanel>
        </div>

        <NocPanel
          title="Validation History"
          action={
            <input
              className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 font-mono text-[11px] text-[var(--fg)]"
              placeholder="Filter ID / result / reason"
              value={filter}
              onChange={(e) => {
                const v = e.target.value;
                startTransition(() => setFilter(v));
              }}
              aria-label="Filter validation history"
            />
          }
        >
          <DeskTable
            columns={[
              "Validation ID",
              "Timestamp",
              "Pipeline",
              "Latency",
              "Result",
              "AI",
              "Reason",
            ]}
            rows={filteredHistory.slice(0, 60).map((row) => {
              const r = asRecord(row);
              return [
                str(r.validation_id, "—"),
                str(r.timestamp, "—").slice(0, 19),
                str(r.pipeline_status || r.final_result, "—"),
                r.latency_ms == null ? "—" : `${r.latency_ms} ms`,
                str(r.result || r.final_result, "—"),
                str(r.ai_action, "—"),
                str(r.reason || r.first_blocker, "—"),
              ];
            })}
          />
          {pending ? (
            <p className="mt-1 text-[10px] text-[var(--fg-subtle)]">Filtering…</p>
          ) : null}
        </NocPanel>
      </div>

      <aside className="lg:sticky lg:top-3 lg:self-start">
        <NocCopilotPanel
          onAsk={(q) => copilot.mutateAsync(q)}
          loading={copilot.isPending}
          result={copilot.data}
          error={copilot.error}
        />
        <div className="mt-3">
          <Button
            size="sm"
            variant="outline"
            className="w-full"
            onClick={() => noc.refetch()}
          >
            Refresh telemetry
          </Button>
        </div>
      </aside>
    </div>
  );
}
