"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Activity,
  AlertTriangle,
  LayoutTemplate,
  Search,
  ShieldAlert,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import {
  iteOpsApi,
  missionControlApi,
  mt5Api,
  platformApi,
  portfolioApi,
} from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { SNAPSHOT_QUERY_KEYS } from "@/lib/api/current-snapshot";
import {
  classifyProtectedFailure,
  protectedFailureCopy,
} from "@/lib/auth/protected-request";
import { asList, asRecord, num, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import {
  overlayExecutiveStatus,
  resolveTradingComponentsView,
} from "@/lib/trading/component-health";
import { useAuth } from "@/providers/auth-provider";
import { cn, formatNumber } from "@/lib/utils";

type PanelView = {
  panel_id: string;
  title: string;
  status: string;
  source: string;
  data: Record<string, unknown>;
  message: string;
};

function FeedEmpty({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <DeskEmpty
      icon={Activity}
      title={title}
      description={description?.trim() || "No live data from production feeds"}
    />
  );
}

function Panel({
  title,
  status,
  children,
  action,
  danger,
}: {
  title: string;
  status?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <section
      className={cn(
        "border bg-[var(--surface)]",
        danger ? "border-[var(--danger)]/50" : "border-[var(--border)]",
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <div className="flex items-center gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            {title}
          </h2>
          {status ? (
            <Badge
              tone={
                status === "available"
                  ? "success"
                  : status === "unavailable"
                    ? "warning"
                    : "neutral"
              }
              className="text-[9px] uppercase tracking-wider"
            >
              {status}
            </Badge>
          ) : null}
        </div>
        {action}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "danger" | "ok" | "muted";
}) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </div>
      <div
        className={cn(
          "mt-0.5 truncate font-mono text-sm tabular-nums",
          tone === "danger" && "text-[var(--danger)]",
          tone === "ok" && "text-[var(--success)]",
          tone === "muted" && "text-[var(--fg-muted)]",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function panelOf(
  dash: Record<string, unknown> | undefined,
  id: string,
): PanelView | null {
  const panels = asRecord(dash?.panels);
  const raw = asRecord(panels[id]);
  if (!raw.panel_id && !raw.title) return null;
  return {
    panel_id: str(raw.panel_id, id),
    title: str(raw.title, id),
    status: str(raw.status, "unavailable"),
    source: str(raw.source, ""),
    data: asRecord(raw.data),
    message: str(raw.message, ""),
  };
}

function fmtMoney(v: unknown): string {
  const n = num(v);
  if (!Number.isFinite(n)) return "—";
  return formatNumber(n, 2);
}

export function MissionControlWorkspace() {
  const { opsReady, authPhase } = useAuth();
  const qc = useQueryClient();
  const [noteText, setNoteText] = useState("");
  const [searchQ, setSearchQ] = useState("");
  const [searchHits, setSearchHits] = useState<Record<string, unknown>[]>([]);

  const accountQ = useQuery({
    queryKey: SNAPSHOT_QUERY_KEYS.mt5Account,
    queryFn: () => mt5Api.account(),
    enabled: opsReady,
    staleTime: 8_000,
    retry: false,
  });

  const positionsQ = useQuery({
    queryKey: SNAPSHOT_QUERY_KEYS.positions,
    queryFn: () => portfolioApi.positions(),
    enabled: opsReady,
    staleTime: 8_000,
    retry: false,
  });

  const tickQ = useQuery({
    queryKey: SNAPSHOT_QUERY_KEYS.tick(TRADING_SYMBOL),
    queryFn: () => mt5Api.tick(TRADING_SYMBOL),
    enabled: opsReady,
    staleTime: 5_000,
    retry: false,
    refetchInterval: opsReady ? 10_000 : false,
  });

  const autoTradingQ = useQuery({
    queryKey: SNAPSHOT_QUERY_KEYS.autoTrading,
    queryFn: () => iteOpsApi.autoTrading(),
    enabled: opsReady,
    staleTime: 8_000,
    retry: false,
  });

  const liveFeeds = useMemo(() => {
    const capital =
      accountQ.data && !accountQ.isError
        ? {
            balance: accountQ.data.balance,
            equity: accountQ.data.equity,
            margin: accountQ.data.margin,
            free_margin: accountQ.data.margin_free ?? accountQ.data.free_margin,
            profit: accountQ.data.profit,
            currency: accountQ.data.currency,
            login: accountQ.data.login,
            server: accountQ.data.server,
          }
        : null;
    const positions =
      positionsQ.data && !positionsQ.isError
        ? (asList(positionsQ.data).map((row) => asRecord(row)) as Record<
            string,
            unknown
          >[])
        : null;
    const xauusd =
      tickQ.data && !tickQ.isError
        ? {
            symbol: TRADING_SYMBOL,
            bid: tickQ.data.bid,
            ask: tickQ.data.ask,
            last: tickQ.data.last,
            time: tickQ.data.time ?? tickQ.data.timestamp,
          }
        : null;
    return { capital, positions, xauusd };
  }, [accountQ.data, accountQ.isError, positionsQ.data, positionsQ.isError, tickQ.data, tickQ.isError]);

  const dashQ = useQuery({
    queryKey: [
      "mission-control-dashboard",
      liveFeeds.capital ? "cap" : "no-cap",
      liveFeeds.positions ? `pos-${liveFeeds.positions.length}` : "no-pos",
      liveFeeds.xauusd ? "tick" : "no-tick",
    ],
    queryFn: () =>
      missionControlApi.dashboardWithFeeds({
        capital: liveFeeds.capital,
        positions: liveFeeds.positions,
        xauusd: liveFeeds.xauusd,
      }),
    enabled: opsReady,
    staleTime: 5_000,
    refetchInterval: opsReady ? 15_000 : false,
  });

  const statusQ = useQuery({
    queryKey: ["mission-control-status"],
    queryFn: () => missionControlApi.status(),
    enabled: opsReady,
    staleTime: 30_000,
  });

  // Authoritative LIVE planes — shares cache with PlatformStatusBoard / AutoRecovery.
  const componentsQ = useQuery({
    queryKey: ["trading-components-health"],
    queryFn: platformApi.tradingComponents,
    staleTime: 20_000,
    refetchInterval: 45_000,
    retry: 1,
    refetchIntervalInBackground: false,
  });
  const authHealth = resolveTradingComponentsView({
    payload: componentsQ.data,
    isSuccess: componentsQ.isSuccess,
    isError: componentsQ.isError,
    errorKind:
      componentsQ.error instanceof ApiError
        ? componentsQ.error.code === "timeout"
          ? "timeout"
          : componentsQ.error.code === "network_error"
            ? "network"
            : "other"
        : componentsQ.isError
          ? "other"
          : null,
  });

  const noteM = useMutation({
    mutationFn: () => missionControlApi.addNote({ text: noteText }),
    onSuccess: async () => {
      setNoteText("");
      toast.success("Note recorded");
      await qc.invalidateQueries({ queryKey: ["mission-control-dashboard"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Note failed"),
  });

  const searchM = useMutation({
    mutationFn: (q: string) => missionControlApi.search(q),
    onSuccess: (data) => {
      setSearchHits(asList(asRecord(data).hits).map((h) => asRecord(h)));
      if (str(asRecord(data).status) === "empty") {
        toast.info(str(asRecord(data).message, "No matches"));
      }
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Search failed"),
  });

  const dash = asRecord(dashQ.data);
  const executive = panelOf(dash, "executive_status");
  const capital = panelOf(dash, "capital_overview");
  const risk = panelOf(dash, "risk_radar");
  const decisions = panelOf(dash, "live_ai_decisions");
  const positions = panelOf(dash, "live_positions");
  const incidents = panelOf(dash, "incident_center");
  const timeline = panelOf(dash, "production_timeline");
  const sysHealth = panelOf(dash, "system_health");
  const aiHealth = panelOf(dash, "ai_health");
  const emergency = panelOf(dash, "emergency_panel");
  const xau = panelOf(dash, "xauusd_watchlist");
  const goldOnly = asRecord(asRecord(autoTradingQ.data).gold_only);
  const goldOnlyMode = goldOnly.gold_only_mode !== false;
  const autonomousSymbol = str(goldOnly.canonical_symbol, TRADING_SYMBOL);
  const daily = panelOf(dash, "daily_summary");
  const notes = panelOf(dash, "operator_notes");
  const fab = panelOf(dash, "floating_action_bar");

  const gatewayDisplay = overlayExecutiveStatus(
    executive?.data.gateway_status ?? sysHealth?.data.gateway_status,
    authHealth?.gateway,
  );
  const mt5Display = overlayExecutiveStatus(
    executive?.data.mt5_status ?? sysHealth?.data.mt5_status,
    authHealth?.mt5,
  );

  const killArmed = Boolean(asRecord(emergency?.data).kill_switch);
  const caps = asRecord(statusQ.data?.capabilities);

  if (!opsReady && (authPhase === "AUTH_LOADING" || authPhase === "AUTH_TIMEOUT")) {
    return <DeskSkeleton rows={8} />;
  }
  if (dashQ.isLoading && !dashQ.data) {
    return <DeskSkeleton rows={8} />;
  }
  if (dashQ.isError && !dashQ.data) {
    const kind = classifyProtectedFailure({
      authPhase,
      opsReady,
      error: dashQ.error,
    });
    const copy = protectedFailureCopy(kind, "Mission Control");
    return (
      <DeskError
        message={`${copy.title}. ${copy.detail}`}
        onRetry={() => void dashQ.refetch()}
      />
    );
  }

  return (
    <div className="relative space-y-3 pb-20">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <LayoutTemplate className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium tracking-wide text-[var(--fg)]">
          Executive dashboard
        </span>
        <Badge tone="neutral" className="text-[9px] uppercase">
          Not Monitoring
        </Badge>
        {caps.fabricate_metrics === false ? (
          <Badge tone="accent" className="text-[9px] uppercase">
            Live feeds only
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(dash.generated_at, "—")}
        </span>
        <Button
          size="sm"
          variant="outline"
          onClick={() => void dashQ.refetch()}
        >
          Refresh
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel
          title="Executive Status"
          status={executive?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/ops">Ops</Link>
            </Button>
          }
        >
          {!executive || executive.status === "unavailable" ? (
            <FeedEmpty title="Unavailable" description={executive?.message} />
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Stat label="System" value={str(executive.data.system_status, "—")} />
              <Stat label="Mode" value={str(executive.data.execution_mode, "—")} />
              <Stat
                label="Kill switch"
                value={str(
                  executive.data.kill_switch_state,
                  executive.data.kill_switch ? "HALT_ALL_TRADING" : "ACTIVE",
                )}
                tone={
                  str(executive.data.kill_switch_state, "ACTIVE") !== "ACTIVE" ||
                  executive.data.kill_switch
                    ? "danger"
                    : "ok"
                }
              />
              <Stat
                label="Burst latch"
                value={
                  asRecord(asRecord(executive.data.phase_a).burst_latch).latched
                    ? "LATCHED"
                    : asRecord(executive.data.phase_a).burst_latch
                      ? "clear"
                      : "—"
                }
                tone={
                  asRecord(asRecord(executive.data.phase_a).burst_latch).latched
                    ? "danger"
                    : "ok"
                }
              />
              <Stat
                label="Recon"
                value={
                  asRecord(asRecord(executive.data.phase_a).reconciliation)
                    .blocking
                    ? "REQUIRED"
                    : asRecord(executive.data.phase_a).reconciliation
                      ? "clear"
                      : "—"
                }
                tone={
                  asRecord(asRecord(executive.data.phase_a).reconciliation)
                    .blocking
                    ? "danger"
                    : "ok"
                }
              />
              <Stat label="Gateway" value={gatewayDisplay} />
              <Stat label="MT5" value={mt5Display} />
              <Stat
                label="OMS"
                value={executive.data.oms_orders_allowed ? "allowed" : "blocked"}
                tone={executive.data.oms_orders_allowed ? "ok" : "danger"}
              />
              <Stat
                label="Data quality"
                value={str(
                  asRecord(asRecord(executive.data.phase_a).market_data).state,
                  "—",
                )}
              />
            </div>
          )}
        </Panel>

        <Panel
          title="Phase B — Performance & Execution Intelligence"
          status={
            asRecord(executive?.data).phase_b
              ? "available"
              : executive?.status === "available"
                ? "empty"
                : executive?.status
          }
        >
          {(() => {
            const phaseB = asRecord(asRecord(executive?.data).phase_b);
            if (!asRecord(executive?.data).phase_b) {
              return (
                <FeedEmpty
                  title="No Phase B feed"
                  description="Observation plane not yet populated — trading connectivity unaffected"
                />
              );
            }
            const portfolio = asRecord(phaseB.portfolio);
            const execution = asRecord(phaseB.execution);
            const maeMfe = asRecord(phaseB.mae_mfe);
            const regime = asRecord(phaseB.regime);
            const strategies = asRecord(phaseB.strategies);
            const parity = asRecord(phaseB.live_vs_research);
            const comparisons = asList(parity.comparisons);
            const journal = asList(phaseB.explain_journal);
            return (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat
                  label="Mode"
                  value={str(phaseB.mode, "OBSERVE")}
                />
                <Stat
                  label="Open MAE/MFE"
                  value={str(maeMfe.open_count, "0")}
                />
                <Stat
                  label="Exec samples"
                  value={str(execution.samples, "0")}
                />
                <Stat
                  label="Exec quality"
                  value={str(execution.avg_execution_quality_score, "—")}
                />
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat
                  label="Open risk"
                  value={str(
                    portfolio.CURRENT_PORTFOLIO_RISK ?? portfolio.current_open_risk,
                    "—",
                  )}
                />
                <Stat
                  label="Incremental"
                  value={str(
                    portfolio.NEW_TRADE_INCREMENTAL_RISK ?? portfolio.new_trade_risk,
                    "—",
                  )}
                />
                <Stat
                  label="Projected"
                  value={str(
                    portfolio.PROJECTED_PORTFOLIO_RISK ??
                      portfolio.projected_total_risk,
                    "—",
                  )}
                />
                <Stat
                  label="USD factors"
                  value={str(
                    asRecord(portfolio.currency_factor_exposure).USD,
                    "—",
                  )}
                />
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Stat
                  label="Regime"
                  value={str(regime.operational_regime, "—")}
                />
                <Stat
                  label="Matrix cells"
                  value={str(strategies.cell_count, "0")}
                />
                <Stat
                  label="Live vs research"
                  value={
                    comparisons.length
                      ? str(asRecord(comparisons[0]).state, "—")
                      : "—"
                  }
                />
              </div>
              <div>
                <p className="mb-1 text-[10px] uppercase tracking-wider text-[var(--fg-subtle)]">
                  Trade explainability (recent)
                </p>
                <ul className="max-h-28 space-y-1 overflow-auto font-mono text-[10px]">
                  {journal.length === 0 ? (
                    <li className="text-[var(--fg-subtle)]">No journal rows yet</li>
                  ) : (
                    journal
                      .slice(-5)
                      .reverse()
                      .map((row, i) => {
                        const r = asRecord(row);
                        return (
                          <li
                            key={str(r.candidate_id, String(i))}
                            className="border-b border-[var(--border)]/50 py-0.5"
                          >
                            <span>{str(r.symbol, "—")}</span>
                            {" · "}
                            <span className="text-[var(--fg-subtle)]">
                              {str(r.WHY_BLOCKED, str(r.WHY_ALLOWED, "—"))}
                            </span>
                          </li>
                        );
                      })
                  )}
                </ul>
              </div>
            </div>
            );
          })()}
        </Panel>

        <Panel
          title="Phase C — Research Integrity & Model Governance"
          status={
            asRecord(executive?.data).phase_c
              ? "available"
              : executive?.status === "available"
                ? "empty"
                : executive?.status
          }
        >
          {(() => {
            const phaseC = asRecord(asRecord(executive?.data).phase_c);
            if (!asRecord(executive?.data).phase_c) {
              return (
                <FeedEmpty
                  title="No Phase C feed"
                  description="Research/shadow plane not yet populated — live trading unaffected"
                />
              );
            }
            const research = asRecord(phaseC.research);
            const challenger = asRecord(phaseC.challenger);
            const promotion = asRecord(phaseC.promotion);
            const provenance = asRecord(research.provenance);
            const latestRun = asRecord(provenance.latest);
            const pbo = asRecord(research.PBO);
            const dsr = asRecord(research.DSR);
            const mc = asRecord(research.monte_carlo);
            const sens = asRecord(research.parameter_sensitivity);
            const leakage = asRecord(research.leakage);
            const drift = asRecord(phaseC.drift);
            const hyp = asRecord(challenger.hypothetical);
            const candidates = asList(promotion.candidates);
            return (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Stat label="Mode" value={str(phaseC.mode, "RESEARCH_SHADOW")} />
                  <Stat
                    label="Challenger exec"
                    value={
                      phaseC.challenger_execution_authority === true
                        ? "TRUE"
                        : "FALSE"
                    }
                    tone={
                      phaseC.challenger_execution_authority === true
                        ? "danger"
                        : "ok"
                    }
                  />
                  <Stat
                    label="PBO"
                    value={str(pbo.state, str(pbo.PBO, "—"))}
                  />
                  <Stat
                    label="DSR"
                    value={str(dsr.CONFIDENCE_STATE, str(dsr.DEFLATED_SHARPE, "—"))}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Stat
                    label="Latest run"
                    value={str(latestRun.research_run_id, "—").slice(0, 8) || "—"}
                  />
                  <Stat label="Dataset" value={str(latestRun.dataset_id, "—")} />
                  <Stat
                    label="Commit"
                    value={str(latestRun.code_commit, "—").slice(0, 8) || "—"}
                  />
                  <Stat
                    label="Trials"
                    value={str(
                      latestRun.trial_count,
                      str(latestRun.number_of_trials, "—"),
                    )}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Stat
                    label="OOS / leakage"
                    value={
                      leakage.oos_certified === true
                        ? "CERTIFIED"
                        : leakage.ok === false
                          ? "FAILED"
                          : str(leakage.state, "—")
                    }
                  />
                  <Stat label="Monte Carlo" value={str(mc.state, "—")} />
                  <Stat label="Sensitivity" value={str(sens.state, "—")} />
                  <Stat
                    label="Provenance"
                    value={str(latestRun.status, str(provenance.count, "0"))}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Stat
                    label="Champion"
                    value={str(asRecord(phaseC.champion).version, "—")}
                  />
                  <Stat
                    label="Challenger"
                    value={str(challenger.challenger_version, "—")}
                  />
                  <Stat
                    label="Shadow samples"
                    value={str(challenger.shadow_samples, "0")}
                  />
                  <Stat
                    label="Hyp expectancy"
                    value={str(hyp.hypothetical_expectancy, "—")}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Stat
                    label="Hyp drawdown"
                    value={str(hyp.hypothetical_drawdown, "—")}
                  />
                  <Stat
                    label="Shadow quality"
                    value={str(hyp.state, "—")}
                  />
                  <Stat
                    label="Drift kinds"
                    value={String(asList(drift.kinds).length || "—")}
                  />
                  <Stat
                    label="Promotion candidates"
                    value={str(promotion.count, "0")}
                  />
                </div>
                <div>
                  <p className="mb-1 text-[10px] uppercase tracking-wider text-[var(--fg-subtle)]">
                    Promotion (recent)
                  </p>
                  <ul className="max-h-24 space-y-1 overflow-auto font-mono text-[10px]">
                    {candidates.length === 0 ? (
                      <li className="text-[var(--fg-subtle)]">No candidates</li>
                    ) : (
                      candidates
                        .slice(-5)
                        .reverse()
                        .map((row, i) => {
                          const r = asRecord(row);
                          return (
                            <li
                              key={str(r.candidate_id, String(i))}
                              className="border-b border-[var(--border)]/50 py-0.5"
                            >
                              <span>{str(r.strategy_id, "—")}</span>
                              {" · "}
                              <span className="text-[var(--fg-subtle)]">
                                {str(r.state, "—")}
                                {r.blocking_reason
                                  ? ` / ${str(r.blocking_reason)}`
                                  : ""}
                              </span>
                            </li>
                          );
                        })
                    )}
                  </ul>
                </div>
              </div>
            );
          })()}
        </Panel>

        <Panel
          title="Phase D — Alpha Governance"
          status={
            asRecord(executive?.data).phase_d
              ? "available"
              : executive?.status === "available"
                ? "empty"
                : executive?.status
          }
        >
          {(() => {
            const phaseD = asRecord(asRecord(executive?.data).phase_d);
            if (!asRecord(executive?.data).phase_d) {
              return (
                <FeedEmpty
                  title="No Phase D feed"
                  description="Alpha governance plane not yet populated — live trading unaffected"
                />
              );
            }
            const candidates = asRecord(phaseD.candidates);
            const canary = asRecord(phaseD.canary);
            const gates = asRecord(phaseD.gates);
            const sample = asRecord(phaseD.sample);
            const approvals = asRecord(phaseD.approvals);
            const rollback = asRecord(phaseD.rollback);
            const canaryRows = asList(canary.records);
            const latestCanary = asRecord(canaryRows[canaryRows.length - 1]);
            return (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Stat label="Mode" value={str(phaseD.mode, "EVIDENCE_GATED")} />
                  <Stat
                    label="Candidate exec"
                    value={
                      phaseD.candidate_execution_authority === true ? "TRUE" : "FALSE"
                    }
                    tone={
                      phaseD.candidate_execution_authority === true ? "danger" : "ok"
                    }
                  />
                  <Stat
                    label="Auto promote"
                    value={phaseD.auto_promote_to_live === true ? "TRUE" : "FALSE"}
                    tone={phaseD.auto_promote_to_live === true ? "danger" : "ok"}
                  />
                  <Stat label="Champion" value={str(asRecord(phaseD.champion).version, "—")} />
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Stat label="Candidates" value={str(candidates.count, "0")} />
                  <Stat label="Promotable" value={str(candidates.promotable, "0")} />
                  <Stat label="Gate result" value={str(gates.result, "—")} />
                  <Stat label="Sample" value={str(sample.state, "—")} />
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Stat label="Canary state" value={str(latestCanary.state, "—")} />
                  <Stat label="Approvals" value={str(approvals.count, "0")} />
                  <Stat label="Rollback" value={str(rollback.action, "—")} />
                  <Stat
                    label="Why blocked"
                    value={str(
                      gates.why_blocked,
                      str(latestCanary.why_blocked, "—"),
                    )}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-2">
                  <Stat
                    label="Why promoted"
                    value={str(latestCanary.why_promoted, "—")}
                  />
                  <Stat
                    label="Why rolled back"
                    value={str(
                      latestCanary.why_rolled_back,
                      str(rollback.why_rolled_back, "—"),
                    )}
                  />
                </div>
              </div>
            );
          })()}
        </Panel>

        <Panel title="Capital Overview" status={capital?.status}>
          {!capital || capital.status !== "available" ? (
            <FeedEmpty
              title={capital?.status === "empty" ? "Empty" : "No live feed"}
              description={capital?.message || "Connect MT5 for account equity"}
            />
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Equity" value={fmtMoney(capital.data.equity)} />
              <Stat label="Balance" value={fmtMoney(capital.data.balance)} />
              <Stat label="Margin free" value={fmtMoney(capital.data.free_margin)} />
              <Stat label="Floating" value={fmtMoney(capital.data.profit)} />
            </div>
          )}
        </Panel>

        <Panel
          title="Risk Radar"
          status={risk?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/risk">Risk desk</Link>
            </Button>
          }
        >
          {!risk || risk.status === "unavailable" ? (
            <FeedEmpty title="Unavailable" description={risk?.message} />
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <Stat
                label="Risk status"
                value={str(risk.data.risk_status, "—")}
              />
              <Stat
                label="Risk / trade"
                value={`${str(risk.data.risk_per_trade_pct, "—")}%`}
              />
              <Stat
                label="Max daily loss"
                value={`${str(risk.data.max_daily_loss_pct, "—")}%`}
              />
              <Stat
                label="Max open"
                value={str(risk.data.max_open_trades, "—")}
              />
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel
          title="Live AI Decisions"
          status={decisions?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/decision-intelligence">Decision Center</Link>
            </Button>
          }
        >
          {!decisions || decisions.status !== "available" ? (
            <FeedEmpty
              title={decisions?.status === "empty" ? "No decisions" : "Unavailable"}
              description={decisions?.message}
            />
          ) : (
            <ul className="max-h-48 space-y-1.5 overflow-auto font-mono text-[11px]">
              {asList(decisions.data.decisions).map((row, i) => {
                const r = asRecord(row);
                return (
                  <li
                    key={str(r.audit_id, String(i))}
                    className="flex justify-between gap-2 border-b border-[var(--border)]/60 py-1"
                  >
                    <span>{str(r.decision, "—")}</span>
                    <span className="text-[var(--fg-subtle)]">
                      {str(r.audit_id, str(r.strategy_id, ""))}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel title="Live Positions" status={positions?.status}>
          {!positions || positions.status !== "available" ? (
            <FeedEmpty
              title={positions?.status === "empty" ? "Flat" : "No live feed"}
              description={positions?.message}
            />
          ) : (
            <ul className="max-h-48 space-y-1.5 overflow-auto font-mono text-[11px]">
              {asList(positions.data.positions).map((row, i) => {
                const r = asRecord(row);
                return (
                  <li
                    key={str(r.ticket ?? r.id, String(i))}
                    className="flex justify-between gap-2 border-b border-[var(--border)]/60 py-1"
                  >
                    <span>
                      {str(r.symbol, TRADING_SYMBOL)} {str(r.side ?? r.type, "")}{" "}
                      {str(r.volume ?? r.lots, "")}
                    </span>
                    <span>{fmtMoney(r.profit ?? r.unrealized_pnl)}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel
          title="Incident Center"
          status={incidents?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/ops">Reliability</Link>
            </Button>
          }
        >
          {!incidents || incidents.status !== "available" ? (
            <FeedEmpty
              title={incidents?.status === "empty" ? "Clear" : "Unavailable"}
              description={incidents?.message}
            />
          ) : (
            <ul className="max-h-44 space-y-1.5 overflow-auto text-[11px]">
              {asList(incidents.data.incidents).map((row, i) => {
                const r = asRecord(row);
                return (
                  <li
                    key={str(r.id, String(i))}
                    className="border-b border-[var(--border)]/60 py-1"
                  >
                    <div className="flex justify-between gap-2 font-mono">
                      <span>{str(r.severity, "—")}</span>
                      <span className="text-[var(--fg-subtle)]">
                        {str(r.status, "")}
                      </span>
                    </div>
                    <div className="text-[var(--fg-muted)]">{str(r.title, "")}</div>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel title="Production Timeline" status={timeline?.status}>
          {!timeline || timeline.status !== "available" ? (
            <FeedEmpty
              title={timeline?.status === "empty" ? "Quiet" : "Unavailable"}
              description={timeline?.message}
            />
          ) : (
            <ul className="max-h-44 space-y-1 overflow-auto font-mono text-[10px]">
              {asList(timeline.data.events).map((row, i) => {
                const r = asRecord(row);
                return (
                  <li key={str(r.id, String(i))} className="truncate py-0.5">
                    <span className="text-[var(--fg-subtle)]">
                      {str(r.timestamp, "").slice(11, 19)}
                    </span>{" "}
                    {str(r.category, "")}/{str(r.action, "")} —{" "}
                    {str(r.detail, "").slice(0, 80)}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel
          title="System Health"
          status={sysHealth?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/monitoring">Monitoring</Link>
            </Button>
          }
        >
          {!sysHealth || sysHealth.status === "unavailable" ? (
            <FeedEmpty title="Unavailable" description={sysHealth?.message} />
          ) : (
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-3">
                <Stat label="Gateway" value={gatewayDisplay} />
                <Stat label="MT5" value={mt5Display} />
                <Stat
                  label="Health score"
                  value={str(sysHealth.data.health_score, "—")}
                />
                <Stat label="Mode" value={str(sysHealth.data.execution_mode, "—")} />
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                {sysHealth.message ||
                  "Executive posture — execution strip lives on Monitoring"}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="AI Health" status={aiHealth?.status}>
          {!aiHealth || aiHealth.status !== "available" ? (
            <FeedEmpty title="Unavailable" description={aiHealth?.message} />
          ) : (
            <ul className="space-y-1 text-[11px]">
              {Object.entries(asRecord(aiHealth.data.modules)).map(([name, body]) => (
                <li
                  key={name}
                  className="flex justify-between border-b border-[var(--border)]/60 py-1 font-mono"
                >
                  <span>{name.replace(/_/g, " ")}</span>
                  <span className="text-[var(--success)]">
                    {asRecord(body).ok ? "online" : "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          title="Emergency Panel"
          status={emergency?.status}
          danger={killArmed}
          action={
            <Button asChild size="sm" variant={killArmed ? "danger" : "outline"}>
              <Link href="/ops">
                <ShieldAlert className="mr-1 size-3.5" />
                Ops control
              </Link>
            </Button>
          }
        >
          {!emergency || emergency.status === "unavailable" ? (
            <FeedEmpty title="Unavailable" description={emergency?.message} />
          ) : (
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-3">
                <Stat
                  label="Kill switch"
                  value={killArmed ? "ARMED" : "clear"}
                  tone={killArmed ? "danger" : "ok"}
                />
                <Stat
                  label="Auto trading"
                  value={str(emergency.data.auto_trading_status, "—")}
                />
                <Stat label="System" value={str(emergency.data.system_status, "—")} />
                <Stat
                  label="OMS"
                  value={emergency.data.oms_orders_allowed ? "allowed" : "blocked"}
                  tone={emergency.data.oms_orders_allowed ? "ok" : "danger"}
                />
              </div>
              <p className="flex items-start gap-1.5 text-[10px] text-[var(--fg-subtle)]">
                <AlertTriangle className="mt-0.5 size-3 shrink-0" />
                {emergency.message}
              </p>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="XAUUSD Watchlist" status={xau?.status}>
          {goldOnlyMode ? (
            <p className="mb-2 font-mono text-[10px] text-[var(--fg-muted)]">
              GOLD ONLY · autonomous {autonomousSymbol} · other pairs disabled
              for autonomous execution
            </p>
          ) : null}
          {!xau || xau.status !== "available" ? (
            <FeedEmpty
              title="No live tick"
              description={xau?.message || "Awaiting MT5 tick"}
            />
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Symbol" value={str(xau.data.symbol, TRADING_SYMBOL)} />
              <Stat label="Bid" value={fmtMoney(xau.data.bid)} />
              <Stat label="Ask" value={fmtMoney(xau.data.ask)} />
              <Stat label="Last" value={fmtMoney(xau.data.last)} />
            </div>
          )}
        </Panel>

        <Panel title="Daily Summary" status={daily?.status}>
          {!daily || daily.status !== "available" ? (
            <FeedEmpty title="No inputs" description={daily?.message} />
          ) : (
            <div className="space-y-2 text-[11px]">
              {daily.data.decision_counts ? (
                <div className="flex flex-wrap gap-2 font-mono">
                  {Object.entries(asRecord(daily.data.decision_counts)).map(
                    ([k, v]) => (
                      <Badge key={k} tone="neutral">
                        {k}: {String(v)}
                      </Badge>
                    ),
                  )}
                </div>
              ) : null}
              <div className="grid grid-cols-2 gap-2">
                <Stat
                  label="Decision events"
                  value={str(daily.data.decision_events, "—")}
                />
                <Stat
                  label="Open incidents"
                  value={str(daily.data.open_incidents, "—")}
                />
                <Stat label="Mode" value={str(daily.data.execution_mode, "—")} />
                <Stat
                  label="Kill"
                  value={daily.data.kill_switch ? "ARMED" : "clear"}
                />
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">{daily.message}</p>
            </div>
          )}
        </Panel>

        <Panel title="Operator Notes" status={notes?.status}>
          <div className="space-y-2">
            <textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              rows={3}
              placeholder="Auditable operator note…"
              className="w-full border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs outline-none focus:border-[var(--fg-muted)]"
            />
            <Button
              size="sm"
              disabled={!noteText.trim() || noteM.isPending}
              onClick={() => noteM.mutate()}
            >
              Record note
            </Button>
            {!notes || notes.status !== "available" ? (
              <FeedEmpty title="No notes" description={notes?.message} />
            ) : (
              <ul className="max-h-36 space-y-1.5 overflow-auto text-[11px]">
                {asList(notes.data.notes).map((row) => {
                  const r = asRecord(row);
                  return (
                    <li
                      key={str(r.note_id)}
                      className="border-b border-[var(--border)]/60 py-1"
                    >
                      <div className="font-mono text-[10px] text-[var(--fg-subtle)]">
                        {str(r.operator)} · {str(r.created_at).slice(0, 19)}
                      </div>
                      <div>{str(r.text)}</div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </Panel>
      </div>

      <Panel
        title="Global Search"
        status="available"
        action={<Search className="size-3.5 text-[var(--fg-subtle)]" />}
      >
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (searchQ.trim()) searchM.mutate(searchQ.trim());
          }}
        >
          <input
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder="Search desks, notes, timeline…"
            className="min-w-[220px] flex-1 border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs outline-none focus:border-[var(--fg-muted)]"
          />
          <Button size="sm" type="submit" disabled={searchM.isPending}>
            Search
          </Button>
        </form>
        {searchHits.length === 0 ? (
          <p className="mt-2 text-[10px] text-[var(--fg-subtle)]">
            Live search across Mission Control desks, operator notes, and
            production timeline events.
          </p>
        ) : (
          <ul className="mt-2 max-h-40 space-y-1 overflow-auto text-[11px]">
            {searchHits.map((h, i) => (
              <li key={`${str(h.href)}-${i}`}>
                <Link
                  href={str(h.href, "/mission-control")}
                  className="flex justify-between gap-2 border-b border-[var(--border)]/60 py-1 hover:text-[var(--fg)]"
                >
                  <span>
                    <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
                      {str(h.kind)}
                    </span>{" "}
                    {str(h.title)}
                  </span>
                  <span className="truncate text-[var(--fg-muted)]">
                    {str(h.detail)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-[var(--border)] bg-[var(--surface)]/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-2 px-3 py-2">
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Actions
          </span>
          {asList(fab?.data.actions).map((row) => {
            const a = asRecord(row);
            const danger = str(a.tone) === "danger";
            return (
              <Button
                key={str(a.href) + str(a.label)}
                asChild
                size="sm"
                variant={danger ? "danger" : "outline"}
              >
                <Link href={str(a.href, "/mission-control")}>{str(a.label)}</Link>
              </Button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
