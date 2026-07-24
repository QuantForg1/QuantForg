"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { iteReliabilityApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "border border-[var(--border)] bg-[var(--surface)]",
        className,
      )}
    >
      <header className="border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="border border-[var(--border)]/70 bg-[var(--bg)] px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
        {label}
      </div>
      <div className="mt-1 font-mono text-lg text-[var(--fg)]">{value}</div>
      {hint ? (
        <div className="mt-0.5 text-[10px] text-[var(--fg-muted)]">{hint}</div>
      ) : null}
    </div>
  );
}

function healthTone(status: string): "success" | "warning" | "danger" | "neutral" {
  const s = status.toLowerCase();
  if (s === "healthy") return "success";
  if (s === "warning") return "warning";
  if (s === "offline") return "danger";
  return "neutral";
}

function severityTone(sev: string): "neutral" | "warning" | "danger" | "success" {
  const s = sev.toUpperCase();
  if (s === "CRITICAL" || s === "ERROR") return "danger";
  if (s === "WARNING") return "warning";
  if (s === "INFO") return "success";
  return "neutral";
}

function fmt(v: unknown, digits = 2): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (Number.isFinite(n)) return n.toFixed(digits);
  return str(v, "—");
}

export function ProductionReliabilityWorkspace() {
  const harden = useQuery({
    queryKey: ["production-hardening-v6"],
    queryFn: iteReliabilityApi.productionHardening,
    retry: false,
    refetchInterval: 15_000,
  });
  const network = useQuery({
    queryKey: ["production-reliability-network"],
    queryFn: iteReliabilityApi.network,
    retry: false,
    refetchInterval: 15_000,
  });

  if (harden.isLoading && network.isLoading) return <DeskSkeleton rows={6} />;
  if (harden.isError && network.isError) {
    return (
      <DeskError message="Reliability dashboard unavailable (OWNER/ADMIN · /ite/reliability/*)." />
    );
  }

  const h = asRecord(harden.data);
  const health = asRecord(h.system_health);
  const perf = asRecord(h.live_performance);
  const risk = asRecord(h.risk_exposure);
  const learn = asRecord(h.learning_status);
  const secrets = asRecord(h.secrets_audit);
  const ops = asRecord(h.ops);
  const ranking = asList(h.opportunity_ranking).map(asRecord);
  const positions = asList(h.open_positions).map(asRecord);
  const timeline = asList(h.execution_timeline).map(asRecord);
  const explanations = asList(h.explanations).map(asRecord);
  const incidents = asList(h.incidents).map(asRecord);
  const compareRoot = asRecord(h.backtest_vs_live);
  const strategies = asList(compareRoot.strategies).map(asRecord);
  const material = asList(compareRoot.material_deviations).map(asRecord);

  const nRoot = asRecord(network.data);
  const net = asRecord(nRoot.network);
  const netIncidents = asList(nRoot.incidents).map(asRecord);
  const reconnects = asList(nRoot.reconnect_log).map(asRecord);

  const healthKeys = [
    ["mt5_gateway", "MT5 Gateway"],
    ["broker", "Broker"],
    ["oms", "OMS"],
    ["auto_trading", "Auto Trading"],
    ["ai_engine", "AI Engine"],
    ["market_data", "Market Data"],
    ["database", "Database"],
    ["railway_service", "Railway"],
  ] as const;

  return (
    <div className="space-y-3">
      <Panel title="System health">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          {healthKeys.map(([key, label]) => {
            const status = str(health[key], "Warning");
            return (
              <div
                key={key}
                className="border border-[var(--border)]/70 bg-[var(--bg)] px-3 py-2"
              >
                <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                  {label}
                </div>
                <div className="mt-1">
                  <Badge tone={healthTone(status)}>{status}</Badge>
                </div>
              </div>
            );
          })}
        </div>
        <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
          Mode {str(ops.mode, "—")} · run {str(ops.auto_trading_run_state, "—")} ·
          trading {str(ops.trading_mode, "—")} · execution{" "}
          {ops.execution_enabled === true ? "on" : "off"}
        </p>
      </Panel>

      <Panel title="Live performance">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <Metric label="Orders submitted" value={str(perf.orders_submitted, "0")} />
          <Metric label="Orders filled" value={str(perf.orders_filled, "0")} />
          <Metric label="Orders rejected" value={str(perf.orders_rejected, "0")} />
          <Metric label="Retry count" value={str(perf.retry_count, "0")} />
          <Metric
            label="Avg latency"
            value={`${fmt(perf.avg_execution_latency_ms, 0)} ms`}
          />
          <Metric label="Avg slippage" value={fmt(perf.avg_slippage, 4)} />
          <Metric label="Avg spread" value={fmt(perf.avg_spread, 4)} />
          <Metric
            label="Win rate"
            value={perf.win_rate == null ? "—" : `${fmt(perf.win_rate, 1)}%`}
          />
          <Metric label="Daily PnL" value={fmt(perf.daily_pnl)} />
          <Metric label="Weekly PnL" value={fmt(perf.weekly_pnl)} />
          <Metric label="Monthly PnL" value={fmt(perf.monthly_pnl)} />
          <Metric
            label="Open / max"
            value={`${str(risk.open_count, "0")} / ${str(risk.max_open, "—")}`}
            hint={
              risk.kill_switch === true
                ? "kill switch"
                : risk.daily_loss_exceeded === true
                  ? "daily loss"
                  : undefined
            }
          />
        </div>
      </Panel>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Opportunity ranking">
          {ranking.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No ranking data.</p>
          ) : (
            <div className="max-h-56 space-y-1 overflow-auto font-mono text-[11px]">
              {ranking.slice(0, 12).map((r) => (
                <div
                  key={str(r.symbol)}
                  className="flex justify-between border-b border-[var(--border)]/40 py-1 last:border-0"
                >
                  <span>
                    #{str(r.rank, "—")} {str(r.symbol)} {str(r.direction)}
                  </span>
                  <span>
                    score {str(r.opportunity_score)} · conf {str(r.ai_confidence)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Open positions">
          {positions.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No managed positions.</p>
          ) : (
            <div className="max-h-56 space-y-1 overflow-auto font-mono text-[11px]">
              {positions.map((p) => (
                <div
                  key={str(p.ticket)}
                  className="border-b border-[var(--border)]/40 py-1 last:border-0"
                >
                  {str(p.symbol)} {str(p.side)} · ticket {str(p.ticket)} · vol{" "}
                  {str(p.remaining_volume)} · BE {p.be_moved === true ? "Y" : "N"} ·
                  trail {p.trailing_active === true ? "Y" : "N"}
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Execution timeline">
          {timeline.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">
              No lifecycle events yet this process.
            </p>
          ) : (
            <div className="max-h-64 space-y-1 overflow-auto font-mono text-[11px]">
              {timeline.slice(0, 40).map((e, idx) => (
                <div
                  key={`${str(e.trace_id)}-${str(e.stage)}-${idx}`}
                  className="border-b border-[var(--border)]/40 py-1 last:border-0"
                >
                  <span className="text-[var(--fg-subtle)]">
                    {str(e.at).slice(11, 19)}
                  </span>{" "}
                  <span className="uppercase">{str(e.stage)}</span>{" "}
                  <Badge tone={e.status === "failed" ? "danger" : "neutral"}>
                    {str(e.status)}
                  </Badge>{" "}
                  {str(e.detail)}
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="AI trade explanations">
          {explanations.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">
              Explanations appear after live fills.
            </p>
          ) : (
            <div className="max-h-64 space-y-2 overflow-auto text-[11px]">
              {explanations.slice(0, 8).map((x) => (
                <div
                  key={str(x.id)}
                  className="border border-[var(--border)]/50 bg-[var(--bg)] p-2"
                >
                  <div className="font-mono">
                    {str(x.symbol)} {str(x.direction)} · ticket {str(x.ticket, "—")}
                  </div>
                  <div className="mt-1 text-[var(--fg-muted)]">
                    Enter: {str(x.why_entered)} · Risk: {str(x.why_risk_pct)} · Lot:{" "}
                    {str(x.why_lot_size)}
                  </div>
                  <div className="text-[var(--fg-muted)]">
                    TP: {str(x.why_tp)} · SL: {str(x.why_sl)} · Conf:{" "}
                    {str(x.why_confidence)}
                  </div>
                  <div className="text-[var(--fg-muted)]">
                    Session: {str(x.why_session)} · Regime: {str(x.why_regime)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <Panel title="Incidents">
          {incidents.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No open hardening incidents.</p>
          ) : (
            <div className="max-h-48 space-y-1 overflow-auto text-[11px]">
              {incidents.map((i) => (
                <div
                  key={str(i.id)}
                  className="border-b border-[var(--border)]/40 py-1 last:border-0"
                >
                  <Badge tone={severityTone(str(i.severity))}>{str(i.severity)}</Badge>{" "}
                  {str(i.title)} — {str(i.detail)}
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Learning status">
          <Metric label="Updates" value={str(learn.updates, "0")} />
          <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
            Gradual Opportunity Score multipliers only — base rules preserved. Enabled:{" "}
            {learn.learning_enabled === false ? "no" : "yes"}.
          </p>
          <div className="mt-2 max-h-32 overflow-auto font-mono text-[10px] text-[var(--fg-muted)]">
            {Object.entries(asRecord(learn.multipliers)).map(([k, v]) => (
              <div key={k}>
                {k}: {fmt(v, 3)}
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Secrets audit">
          <p className="text-sm text-[var(--fg-muted)]">
            Values never shown. Present names:{" "}
            {asList(secrets.sensitive_env_names_present).length}. Empty:{" "}
            {asList(secrets.sensitive_env_names_empty).length}.
          </p>
          <div className="mt-2 max-h-32 overflow-auto font-mono text-[10px]">
            {asList(secrets.sensitive_env_names_present)
              .slice(0, 24)
              .map((name) => (
                <div key={str(name)}>{str(name)}</div>
              ))}
          </div>
        </Panel>
      </div>

      <Panel title="Backtest vs live">
        {strategies.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">
            No strategy comparison snapshots yet.
          </p>
        ) : (
          <div className="space-y-2">
            {material.length > 0 ? (
              <p className="text-[11px] text-[var(--danger)]">
                Material deviations: {material.length}
              </p>
            ) : (
              <p className="text-[11px] text-[var(--fg-muted)]">
                No material deviations flagged.
              </p>
            )}
            <div className="max-h-40 overflow-auto font-mono text-[11px]">
              {strategies.map((s) => {
                const d = asRecord(s.deviations);
                return (
                  <div
                    key={str(s.strategy_id)}
                    className="border-b border-[var(--border)]/40 py-1 last:border-0"
                  >
                    {str(s.strategy_id)} · BT WR {fmt(s.backtest_win_rate, 1)} → Live{" "}
                    {fmt(s.live_win_rate, 1)} · Δ {fmt(d.win_rate_delta, 1)}
                    {d.material_deviation === true ? " · MATERIAL" : ""}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </Panel>

      <Panel title="Network reliability">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <Metric
            label="Gateway uptime"
            value={`${num(net.gateway_uptime_pct, 100).toFixed(2)}%`}
            hint={net.gateway_currently_up ? "UP" : "DOWN"}
          />
          <Metric label="DNS failures (24h)" value={str(net.dns_failures_24h, "0")} />
          <Metric label="Reconnect count" value={str(net.reconnect_count, "0")} />
          <Metric
            label="Avg reconnect"
            value={`${num(net.average_reconnect_time_ms, 0).toFixed(0)} ms`}
          />
          <Metric
            label="MT5 uptime"
            value={`${num(net.mt5_connection_uptime_pct, 100).toFixed(2)}%`}
          />
          <Metric
            label="Network incidents"
            value={str(netIncidents.length)}
            hint={`${reconnects.length} reconnects`}
          />
        </div>
      </Panel>
    </div>
  );
}
