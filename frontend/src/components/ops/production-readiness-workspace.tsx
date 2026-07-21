"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Shield, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import {
  iteOpsApi,
  iteReliabilityApi,
  mt5Api,
  portfolioApi,
  productionReadinessApi,
} from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

type PanelView = {
  panel_id: string;
  title: string;
  status: string;
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
      icon={Shield}
      title={title}
      description={description?.trim() || "No readiness data"}
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

function panelOf(
  dash: Record<string, unknown> | undefined,
  id: string,
): PanelView | null {
  const raw = asRecord(asRecord(dash?.panels)[id]);
  if (!raw.panel_id && !raw.title) return null;
  return {
    panel_id: str(raw.panel_id, id),
    title: str(raw.title, id),
    status: str(raw.status, "unavailable"),
    data: asRecord(raw.data),
    message: str(raw.message, ""),
  };
}

export function ProductionReadinessWorkspace() {
  const qc = useQueryClient();
  const [minScore, setMinScore] = useState("80");

  const mt5Q = useQuery({
    queryKey: ["pr-mt5-status"],
    queryFn: () => mt5Api.status(),
    staleTime: 10_000,
    retry: false,
  });
  const historyQ = useQuery({
    queryKey: ["pr-portfolio-history"],
    queryFn: () => portfolioApi.history(),
    staleTime: 20_000,
    retry: false,
  });
  const shadowQ = useQuery({
    queryKey: ["pr-shadow-readiness"],
    queryFn: () => iteReliabilityApi.shadowReadiness(),
    staleTime: 20_000,
    retry: false,
  });

  const liveFeeds = useMemo(() => {
    const mt5 = asRecord(mt5Q.data);
    const connected =
      mt5Q.isError || !mt5Q.data
        ? null
        : Boolean(mt5.connected ?? mt5.online ?? mt5.ok);
    const pre_trade_facts =
      mt5Q.isError && !mt5Q.data
        ? null
        : {
            broker_connected: connected,
            market_open: null,
            risk_passed: null,
            margin_sufficient: null,
            strategy_signal_valid: null,
            execution_enabled: false,
            risk_engine_passed: null,
            safety_engine_passed: null,
          };
    const deals = asList(
      asRecord(historyQ.data).deals ??
        asRecord(historyQ.data).history_deals ??
        asRecord(historyQ.data).trades,
    ).map((r) => asRecord(r));
    const post_trade_rows =
      historyQ.data && !historyQ.isError
        ? deals
            .filter((d) => str(d.symbol, TRADING_SYMBOL) === TRADING_SYMBOL)
            .slice(0, 20)
        : null;
    return {
      pre_trade_facts,
      post_trade_rows,
      shadow_readiness:
        shadowQ.data && !shadowQ.isError ? asRecord(shadowQ.data) : null,
    };
  }, [
    mt5Q.data,
    mt5Q.isError,
    historyQ.data,
    historyQ.isError,
    shadowQ.data,
    shadowQ.isError,
  ]);

  const dashQ = useQuery({
    queryKey: [
      "production-readiness-dashboard",
      liveFeeds.pre_trade_facts ? "pre" : "no-pre",
      liveFeeds.post_trade_rows?.length ?? "post",
      shadowQ.isSuccess,
    ],
    queryFn: () => productionReadinessApi.dashboardWithFeeds(liveFeeds),
    staleTime: 8_000,
    refetchInterval: 20_000,
  });

  const statusQ = useQuery({
    queryKey: ["production-readiness-status"],
    queryFn: () => productionReadinessApi.status(),
    staleTime: 30_000,
  });

  const policiesQ = useQuery({
    queryKey: ["production-readiness-policies"],
    queryFn: () => productionReadinessApi.policies(),
    staleTime: 30_000,
  });

  const policyM = useMutation({
    mutationFn: () =>
      productionReadinessApi.updatePolicies({
        min_health_score: Number(minScore) || 80,
      }),
    onSuccess: async () => {
      toast.success("Health policies updated (Risk/Safety locks unchanged)");
      await qc.invalidateQueries({ queryKey: ["production-readiness"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Policy update failed"),
  });

  const recoverM = useMutation({
    mutationFn: async (kind: "gateway" | "mt5" | "safe-read") => {
      let result: Record<string, unknown> = {};
      if (kind === "gateway") {
        result = asRecord(await iteReliabilityApi.recoverGateway());
      } else if (kind === "mt5") {
        result = asRecord(await iteReliabilityApi.recoverMt5());
      } else {
        result = asRecord(await iteReliabilityApi.recoverSafeRead());
      }
      await productionReadinessApi.logRecovery({
        action: kind,
        ok: Boolean(result.ok ?? result.success ?? true),
        detail: str(result.detail ?? result.message, `${kind} recovery invoked`),
        meta: result,
      });
      return result;
    },
    onSuccess: async () => {
      toast.success("Recovery invoked and logged");
      await qc.invalidateQueries({
        queryKey: ["production-readiness-dashboard"],
      });
    },
    onError: async (e) => {
      const msg = e instanceof ApiError ? e.message : "Recovery failed";
      toast.error(msg);
      try {
        await productionReadinessApi.logFailure({
          action: "recovery",
          detail: msg,
        });
      } catch {
        /* audit best-effort */
      }
    },
  });

  const runbookM = useMutation({
    mutationFn: (id: string) => iteOpsApi.executeRunbook(id),
    onSuccess: () => toast.info("Runbook checklist opened via Ops"),
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Runbook failed"),
  });

  const dash = asRecord(dashQ.data);
  const caps = asRecord(statusQ.data?.capabilities);
  const pre = panelOf(dash, "pre_trade_validation");
  const post = panelOf(dash, "post_trade_validation");
  const breakers = panelOf(dash, "circuit_breakers");
  const health = panelOf(dash, "platform_health_policies");
  const recovery = panelOf(dash, "automatic_recovery");
  const incidents = panelOf(dash, "incident_manager");
  const playbooks = panelOf(dash, "operator_playbooks");
  const deploy = panelOf(dash, "deployment_verification");
  const security = panelOf(dash, "security_hardening");
  const dr = panelOf(dash, "disaster_recovery");
  const killArmed = Boolean(asRecord(breakers?.data).kill_switch);

  if (dashQ.isLoading && !dashQ.data) return <DeskSkeleton rows={8} />;
  if (dashQ.isError && !dashQ.data) {
    return (
      <DeskError
        message={
          dashQ.error instanceof ApiError
            ? dashQ.error.message
            : "Production Readiness unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <Shield className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">Production reliability desk</span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Never order_send
        </Badge>
        {caps.bypass_risk === false ? (
          <Badge tone="success" className="text-[9px] uppercase">
            Risk locked
          </Badge>
        ) : null}
        {caps.bypass_safety === false ? (
          <Badge tone="success" className="text-[9px] uppercase">
            Safety locked
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(dash.generated_at, "—")}
        </span>
        <Button size="sm" variant="outline" onClick={() => void dashQ.refetch()}>
          Refresh
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel title="Pre-Trade Validation Checklist" status={pre?.status}>
          {!pre || pre.status !== "available" ? (
            <FeedEmpty
              title={pre?.status === "empty" ? "Empty" : "Unavailable"}
              description={pre?.message}
            />
          ) : (
            <div className="space-y-2 text-[11px]">
              <p className="text-[var(--fg-subtle)]">{pre.message}</p>
              <Badge tone={pre.data.blocked ? "danger" : "success"}>
                {pre.data.ready_for_execution ? "ready" : "not ready"}
              </Badge>
              <ul className="max-h-40 space-y-1 overflow-auto font-mono text-[10px]">
                {asList(pre.data.items).map((row) => {
                  const r = asRecord(row);
                  return (
                    <li key={str(r.key)} className="flex justify-between">
                      <span>{str(r.key)}</span>
                      <span>{str(r.status)}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </Panel>

        <Panel
          title="Post-Trade Validation Checklist"
          status={post?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/execution-intel">Execution Intel</Link>
            </Button>
          }
        >
          {!post || post.status !== "available" ? (
            <FeedEmpty
              title={post?.status === "empty" ? "No trades" : "Unavailable"}
              description={post?.message}
            />
          ) : (
            <div className="text-[11px]">
              <div className="mb-1 font-mono">
                trades: {str(post.data.trade_count, "0")}
              </div>
              <ul className="max-h-40 space-y-1 overflow-auto font-mono text-[10px]">
                {asList(post.data.items)
                  .slice(0, 12)
                  .map((row, i) => {
                    const r = asRecord(row);
                    return (
                      <li key={`${str(r.key)}-${i}`}>
                        {str(r.key)} · {str(r.status)}
                      </li>
                    );
                  })}
              </ul>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel
          title="Circuit Breakers"
          status={breakers?.status}
          danger={killArmed}
          action={
            <Button asChild size="sm" variant={killArmed ? "danger" : "outline"}>
              <Link href="/ops">
                <ShieldAlert className="mr-1 size-3.5" />
                Ops
              </Link>
            </Button>
          }
        >
          {!breakers || breakers.status !== "available" ? (
            <FeedEmpty title="Unavailable" description={breakers?.message} />
          ) : (
            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
              <div>kill: {killArmed ? "ARMED" : "clear"}</div>
              <div>mode: {str(breakers.data.execution_mode, "—")}</div>
              <div>
                oms:{" "}
                {breakers.data.oms_orders_allowed ? "allowed" : "blocked"}
              </div>
              <div>
                daily loss:{" "}
                {breakers.data.daily_loss_exceeded ? "exceeded" : "ok"}
              </div>
              <p className="col-span-2 text-[10px] text-[var(--fg-subtle)]">
                {breakers.message}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="Platform Health Policies" status={health?.status}>
          <div className="mb-2 flex flex-wrap gap-2">
            <input
              value={minScore}
              onChange={(e) => setMinScore(e.target.value)}
              className="w-24 border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-xs"
              aria-label="Min health score"
            />
            <Button
              size="sm"
              variant="outline"
              disabled={policyM.isPending}
              onClick={() => policyM.mutate()}
            >
              Set min score
            </Button>
          </div>
          {!health || health.status !== "available" ? (
            <FeedEmpty title="Unavailable" description={health?.message} />
          ) : (
            <div className="space-y-2 text-[11px]">
              <p className="text-[var(--fg-subtle)]">{health.message}</p>
              <Badge
                tone={
                  asRecord(health.data.evaluation).passed ? "success" : "danger"
                }
              >
                policy{" "}
                {asRecord(health.data.evaluation).passed ? "pass" : "fail"}
              </Badge>
              <pre className="max-h-36 overflow-auto border border-[var(--border)] bg-[var(--bg)] p-2 font-mono text-[10px]">
                {JSON.stringify(
                  {
                    policies:
                      asRecord(policiesQ.data).policies ?? health.data.policies,
                    evaluation: health.data.evaluation,
                  },
                  null,
                  2,
                )}
              </pre>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel title="Automatic Recovery Workflows" status={recovery?.status}>
          <div className="mb-2 flex flex-wrap gap-2">
            {(["gateway", "mt5", "safe-read"] as const).map((kind) => (
              <Button
                key={kind}
                size="sm"
                variant="outline"
                disabled={recoverM.isPending}
                onClick={() => recoverM.mutate(kind)}
              >
                Recover {kind}
              </Button>
            ))}
          </div>
          {!recovery || recovery.status === "unavailable" ? (
            <FeedEmpty title="Unavailable" description={recovery?.message} />
          ) : (
            <div className="text-[11px]">
              <p className="mb-1 text-[var(--fg-subtle)]">{recovery.message}</p>
              <ul className="max-h-32 space-y-1 overflow-auto font-mono text-[10px]">
                {asList(recovery.data.events).map((row, i) => {
                  const r = asRecord(row);
                  return (
                    <li key={str(r.id, String(i))}>
                      {str(r.action, "—")} · {String(r.ok)} ·{" "}
                      {str(r.detail, "").slice(0, 60)}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </Panel>

        <Panel
          title="Incident Manager"
          status={incidents?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/ops">Ops</Link>
            </Button>
          }
        >
          {!incidents || incidents.status !== "available" ? (
            <FeedEmpty
              title={incidents?.status === "empty" ? "Clear" : "Unavailable"}
              description={incidents?.message}
            />
          ) : (
            <ul className="max-h-40 space-y-1 overflow-auto text-[11px]">
              {asList(incidents.data.incidents).map((row, i) => {
                const r = asRecord(row);
                return (
                  <li
                    key={str(r.id, String(i))}
                    className="border-b border-[var(--border)]/60 py-1"
                  >
                    <div className="font-mono text-[10px]">
                      {str(r.severity)} · {str(r.status)}
                    </div>
                    <div>{str(r.title)}</div>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel title="Operator Playbooks" status={playbooks?.status}>
          {!playbooks || playbooks.status !== "available" ? (
            <FeedEmpty title="Unavailable" description={playbooks?.message} />
          ) : (
            <ul className="space-y-1 text-[11px]">
              {asList(playbooks.data.runbooks).map((row) => {
                const r = asRecord(row);
                const id = str(r.id);
                return (
                  <li
                    key={id}
                    className="flex items-center justify-between border-b border-[var(--border)]/60 py-1"
                  >
                    <span>{str(r.title, id)}</span>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={!id || runbookM.isPending}
                      onClick={() => runbookM.mutate(id)}
                    >
                      Open
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel title="Deployment Verification Dashboard" status={deploy?.status}>
          {!deploy || deploy.status === "unavailable" ? (
            <FeedEmpty title="Unavailable" description={deploy?.message} />
          ) : (
            <div className="space-y-2 text-[11px] font-mono">
              <div>mode: {str(deploy.data.execution_mode, "—")}</div>
              <div>config: {str(deploy.data.config_version, "—")}</div>
              <div>strategy: {str(deploy.data.strategy_version, "—")}</div>
              <div>git: {str(deploy.data.git_commit, "—")}</div>
              <div>
                go/nogo:{" "}
                {str(asRecord(deploy.data.go_nogo).status, "—")}
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">{deploy.message}</p>
              <Button asChild size="sm" variant="outline">
                <Link href="/ops">Open certification on Ops</Link>
              </Button>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel title="Security Hardening" status={security?.status}>
          {!security || security.status !== "available" ? (
            <FeedEmpty title="Unavailable" description={security?.message} />
          ) : (
            <div className="space-y-2 text-[11px]">
              <pre className="max-h-36 overflow-auto border border-[var(--border)] bg-[var(--bg)] p-2 font-mono text-[10px]">
                {JSON.stringify(security.data.hard_locks, null, 2)}
              </pre>
              <div className="flex flex-wrap gap-2">
                <Button asChild size="sm" variant="outline">
                  <Link href="/settings">Settings</Link>
                </Button>
                <Button asChild size="sm" variant="outline">
                  <Link href="/gateway">Gateway</Link>
                </Button>
              </div>
            </div>
          )}
        </Panel>

        <Panel
          title="Disaster Recovery Center"
          status={dr?.status}
          action={
            <Button asChild size="sm" variant="danger">
              <Link href="/ops">Emergency Ops</Link>
            </Button>
          }
        >
          {!dr || dr.status === "unavailable" ? (
            <FeedEmpty title="Unavailable" description={dr?.message} />
          ) : (
            <div className="space-y-2 text-[11px]">
              <p className="text-[var(--fg-subtle)]">{dr.message}</p>
              <ul className="max-h-32 space-y-1 overflow-auto font-mono text-[10px]">
                {asList(dr.data.runbooks).map((row) => {
                  const r = asRecord(row);
                  return <li key={str(r.id)}>{str(r.title, str(r.id))}</li>;
                })}
              </ul>
              <div className="text-[10px] text-[var(--fg-subtle)]">
                recovery events: {asList(dr.data.recovery_events).length} ·
                audit: {asList(dr.data.ops_audit_tail).length} · never retry
                orders: {String(dr.data.never_retries_order_send)}
              </div>
            </div>
          )}
        </Panel>
      </div>

      {asList(dash.audit_tail).length > 0 ? (
        <Panel title="Readiness Audit Tail" status="available">
          <ul className="max-h-28 space-y-1 overflow-auto font-mono text-[10px]">
            {asList(dash.audit_tail).map((row) => {
              const r = asRecord(row);
              return (
                <li key={str(r.event_id)}>
                  {str(r.created_at).slice(11, 19)} · {str(r.action)} ·{" "}
                  {String(r.ok)} · {str(r.detail).slice(0, 80)}
                </li>
              );
            })}
          </ul>
        </Panel>
      ) : null}
    </div>
  );
}
