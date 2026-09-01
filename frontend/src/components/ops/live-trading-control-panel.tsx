"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { liveTradingControlApi } from "@/lib/api/endpoints";
import { iteOpsAccessDeniedMessage } from "@/lib/auth/ite-ops-access";
import { useAuth } from "@/providers/auth-provider";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const CONFIRM_PHRASE = "I UNDERSTAND THIS USES REAL MONEY";

type LiveState =
  | "DISABLED"
  | "READY_FOR_REVIEW"
  | "ARMED"
  | "ENABLED"
  | "LIVE_ENABLED"
  | "PAUSED"
  | "KILLED"
  | "EMERGENCY_STOP";

function toneForState(
  state: string,
): "success" | "warning" | "danger" | "neutral" | "accent" {
  if (state === "ENABLED" || state === "LIVE_ENABLED") return "danger";
  if (state === "READY_FOR_REVIEW") return "accent";
  if (state === "ARMED") return "accent";
  if (state === "PAUSED") return "warning";
  if (state === "KILLED" || state === "EMERGENCY_STOP") return "danger";
  return "neutral";
}

function connTone(ok: boolean): "success" | "danger" {
  return ok ? "success" : "danger";
}

const BLOCKER_LABELS: Record<string, string> = {
  gateway_offline: "Gateway is offline.",
  mt5_disconnected: "MT5 is disconnected.",
  mt5_not_attached: "MT5 is not attached.",
  broker_ownership_failure: "Broker account is not owned by this operator.",
  account_unavailable: "Broker account details are unavailable.",
  equity_unavailable: "Account equity is unavailable or not positive.",
  balance_unavailable: "Account balance is unavailable or not positive.",
  restart_recovery: "Restart recovery — waiting for broker, MT5, and account probes.",
  safety_pause: "Safety pause — waiting for gateway, MT5, or ownership to recover.",
  operator: "Operator paused live trading. Resume requires ENABLE confirmation.",
};

function blockerCopy(code: string): string {
  return BLOCKER_LABELS[code] || code;
}

export function LiveTradingControlPanel() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [reason, setReason] = useState("operator live-trading control");
  const [phrase, setPhrase] = useState("");
  const [ack, setAck] = useState(false);
  const [step, setStep] = useState<"idle" | "arm" | "enable" | "kill">("idle");

  const statusQ = useQuery({
    queryKey: ["live-trading-control"],
    queryFn: liveTradingControlApi.status,
    retry: false,
    refetchInterval: 12_000,
  });

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["live-trading-control"] });
    void qc.invalidateQueries({ queryKey: ["ite-ops-auto-trading"] });
  };

  const armMut = useMutation({
    mutationFn: () =>
      liveTradingControlApi.arm({
        reason,
        confirmed: true,
        confirmation_phrase: phrase,
      }),
    onSuccess: () => {
      setStep("idle");
      setPhrase("");
      setAck(false);
      invalidate();
    },
  });
  const enableMut = useMutation({
    mutationFn: () =>
      liveTradingControlApi.enable({
        reason,
        confirmed: true,
        confirmation_phrase: phrase,
      }),
    onSuccess: () => {
      setStep("idle");
      setPhrase("");
      setAck(false);
      invalidate();
    },
  });
  const pauseMut = useMutation({
    mutationFn: () => liveTradingControlApi.pause(reason || "pause"),
    onSuccess: invalidate,
  });
  const disableMut = useMutation({
    mutationFn: () => liveTradingControlApi.disable(reason || "disable"),
    onSuccess: invalidate,
  });
  const killMut = useMutation({
    mutationFn: () =>
      liveTradingControlApi.emergencyStop(reason || "emergency_stop", true),
    onSuccess: () => {
      setStep("idle");
      invalidate();
    },
  });
  const resetMut = useMutation({
    mutationFn: () => liveTradingControlApi.resetKilled(reason || "reset_killed"),
    onSuccess: invalidate,
  });

  if (statusQ.isLoading) return <DeskSkeleton rows={6} />;
  if (statusQ.isError) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(
          user,
          statusQ.error,
          "Live trading controls",
        )}
      />
    );
  }

  const d = asRecord(statusQ.data);
  const canonical = str(d.live_trading_state, "DISABLED").toUpperCase();
  const state = str(d.display_state, canonical).toUpperCase() as LiveState;
  const liveConfirmed = canonical === "ENABLED" || canonical === "LIVE_ENABLED";
  const broker = asRecord(d.broker);
  const gateway = asRecord(d.gateway);
  const mt5 = asRecord(d.mt5);
  const ownership = asRecord(d.ownership);
  const account = asRecord(d.account);
  const risk = asRecord(d.risk);
  const execution = asRecord(d.execution);
  const research = asRecord(d.research);
  const signals = asList(d.signals).map(asRecord);
  const gates = asList(d.safety_gates).map(asRecord);
  const confirm = asRecord(d.confirmation_required);
  const phraseOk = phrase.trim() === CONFIRM_PHRASE;
  const pending =
    armMut.isPending ||
    enableMut.isPending ||
    pauseMut.isPending ||
    disableMut.isPending ||
    killMut.isPending ||
    resetMut.isPending;

  const errorText = str(
    (armMut.error as { message?: string } | null)?.message ||
      (enableMut.error as { message?: string } | null)?.message ||
      (killMut.error as { message?: string } | null)?.message ||
      "",
    "",
  );

  return (
    <div className="space-y-4">
      <Card
        className={cn(
          liveConfirmed && "border-[var(--danger)]",
          (state === "KILLED" ||
            state === "EMERGENCY_STOP" ||
            Boolean(d.kill_switch)) &&
            "border-[var(--danger)]",
          state === "PAUSED" && "border-[var(--warning)]",
        )}
      >
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-2 text-base">
            LIVE TRADING
            <Badge tone={toneForState(liveConfirmed ? "LIVE_ENABLED" : state)}>
              {liveConfirmed ? "ACTIVE" : state}
            </Badge>
            <Badge tone="neutral">
              research_can_execute = {d.research_can_execute ? "true" : "false"}
            </Badge>
            <Badge tone="neutral">
              allow_live_promotion = {d.allow_live_promotion ? "true" : "false"}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-xs text-[var(--fg-muted)]">
            Backend state is authoritative. ACTIVE is shown only when the
            server confirms ENABLED. Research stays advisory. This page never
            enables trading on load. Capital preservation is the priority.
            Returns are not promised.
          </p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <StatusTile
              label="Broker"
              value={str(broker.status, "DISCONNECTED")}
              ok={str(broker.status) === "CONNECTED"}
            />
            <StatusTile
              label="Gateway"
              value={str(gateway.status, "OFFLINE")}
              ok={str(gateway.status) === "ONLINE"}
            />
            <StatusTile
              label="MT5"
              value={str(mt5.status, "DETACHED")}
              ok={str(mt5.status) === "ATTACHED"}
            />
            <StatusTile
              label="Ownership"
              value={str(ownership.status, "NOT_OWNED")}
              ok={str(ownership.status) === "OWNED"}
            />
            <StatusTile
              label="Risk Engine"
              value={
                gates.some((g) => str(g.key) === "risk_engine_healthy" && g.passed === true)
                  ? "READY"
                  : "NOT READY"
              }
              ok={gates.some(
                (g) => str(g.key) === "risk_engine_healthy" && g.passed === true,
              )}
            />
            <StatusTile
              label="OMS"
              value={
                gates.some((g) => str(g.key) === "oms_healthy" && g.passed === true)
                  ? "HEALTHY"
                  : "NOT HEALTHY"
              }
              ok={gates.some((g) => str(g.key) === "oms_healthy" && g.passed === true)}
            />
            <StatusTile
              label="Robot"
              value={liveConfirmed ? "ACTIVE" : state}
              ok={liveConfirmed}
            />
            <StatusTile
              label="Kill switch"
              value={d.kill_switch ? "LATCHED" : "READY"}
              ok={!Boolean(d.kill_switch)}
            />
            <StatusTile
              label="Orders may submit"
              value={d.orders_may_submit ? "TRUE" : "FALSE"}
              ok={Boolean(d.orders_may_submit)}
            />
          </div>
          {!liveConfirmed ? (
            <div className="rounded-[var(--radius-sm)] border border-[var(--warning)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--fg)]">
              <p className="font-medium text-[var(--warning)]">Activation blocker</p>
              {str(d.pause_reason, "") ? (
                <p>{blockerCopy(str(d.pause_reason))}</p>
              ) : null}
              {asList(d.activation_blockers).length > 0 ? (
                <ul className="mt-1 list-disc pl-4">
                  {asList(d.activation_blockers).map((item) => (
                    <li key={String(item)}>{blockerCopy(String(item))}</li>
                  ))}
                </ul>
              ) : str(d.activation_blocker, "") ? (
                <p>{blockerCopy(str(d.activation_blocker))}</p>
              ) : str(d.pause_reason, "") ? null : (
                <p>Live trading is not ENABLED. ARM and ENABLE remain required.</p>
              )}
            </div>
          ) : null}
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Balance" value={str(account.balance, "—")} />
            <Metric label="Equity" value={str(account.equity, "—")} />
            <Metric label="Available margin" value={str(account.free_margin, "—")} />
            <Metric label="Open positions" value={str(account.open_positions, "0")} />
            <Metric
              label="Today's P/L"
              value={
                str(account.daily_pnl_status, "") === "UNAVAILABLE"
                  ? "UNAVAILABLE / VERIFYING"
                  : str(account.daily_pnl, "—")
              }
            />
            <Metric
              label="Today's loss %"
              value={
                str(account.daily_pnl_status, "") === "UNAVAILABLE"
                  ? "UNAVAILABLE / VERIFYING"
                  : str(risk.daily_loss_used_pct, "—")
              }
            />
            <Metric label="Risk / trade" value={`${str(risk.risk_per_trade_pct, "—")}%`} />
            <Metric label="Daily loss limit" value={`${str(risk.max_daily_loss_pct, "—")}%`} />
            <Metric
              label="Remaining daily budget"
              value={str(risk.remaining_daily_risk_budget, "—")}
            />
            <Metric label="Max positions" value={str(risk.max_open_positions, "1")} />
            <Metric
              label="Consecutive losses"
              value={`${str(risk.consecutive_losses, "0")} / ${str(risk.max_consecutive_losses, "2")}`}
            />
            <Metric label="Margin level" value={str(account.margin_level, "—")} />
          </div>

          {gates.length > 0 ? (
            <div>
              <p className="mb-2 text-[10px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                Safety gates
              </p>
              <ul className="grid gap-1 sm:grid-cols-2">
                {gates.map((g) => {
                  const status = str(g.status, "FAIL");
                  const passed = g.passed === true;
                  return (
                    <li
                      key={str(g.key)}
                      className="flex items-center justify-between gap-2 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-xs"
                    >
                      <span>{str(g.label, str(g.key))}</span>
                      <Badge
                        tone={
                          status === "PER_ORDER"
                            ? "neutral"
                            : passed
                              ? "success"
                              : "danger"
                        }
                      >
                        {status === "PER_ORDER"
                          ? "PER ORDER"
                          : passed
                            ? "PASS"
                            : "FAIL"}
                      </Badge>
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}
          {str(execution.last_rejection_reason, "") !== "—" &&
          str(execution.last_rejection_reason, "") ? (
            <p className="text-xs text-[var(--warning)]">
              Last rejection: {str(execution.last_rejection_reason)}
            </p>
          ) : null}

          <label className="block text-xs text-[var(--fg-muted)]">
            Reason
            <input
              className="mt-1 w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--fg)]"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>

          {step !== "idle" ? (
            <ConfirmationBlock
              title={
                step === "kill"
                  ? "Confirm EMERGENCY STOP"
                  : step === "arm"
                    ? "Confirm ARM LIVE TRADING"
                    : "Confirm ENABLE LIVE TRADING"
              }
              confirm={confirm}
              broker={broker}
              account={account}
              risk={risk}
              phrase={phrase}
              setPhrase={setPhrase}
              ack={ack}
              setAck={setAck}
              phraseOk={phraseOk}
              pending={pending}
              onCancel={() => {
                setStep("idle");
                setPhrase("");
                setAck(false);
              }}
              onConfirm={() => {
                if (step === "arm") armMut.mutate();
                if (step === "enable") enableMut.mutate();
                if (step === "kill") killMut.mutate();
              }}
              danger={step === "kill" || step === "enable"}
            />
          ) : (
            <div className="flex flex-wrap gap-2">
              {canonical === "DISABLED" || canonical === "READY_FOR_REVIEW" ? (
                <Button type="button" onClick={() => setStep("arm")} disabled={pending}>
                  ARM LIVE TRADING
                </Button>
              ) : null}
              {canonical === "ARMED" ? (
                <Button type="button" onClick={() => setStep("enable")} disabled={pending}>
                  ENABLE LIVE TRADING
                </Button>
              ) : null}
              {canonical === "ENABLED" || canonical === "LIVE_ENABLED" ? (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => pauseMut.mutate()}
                  disabled={pending}
                >
                  Pause
                </Button>
              ) : null}
              {canonical === "PAUSED" ? (
                <Button type="button" onClick={() => setStep("enable")} disabled={pending}>
                  Resume (ENABLE)
                </Button>
              ) : null}
              {canonical !== "DISABLED" ? (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => disableMut.mutate()}
                  disabled={pending || canonical === "KILLED"}
                >
                  DISABLE LIVE TRADING
                </Button>
              ) : null}
              {canonical === "KILLED" ? (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => resetMut.mutate()}
                  disabled={pending}
                >
                  Reset to DISABLED
                </Button>
              ) : null}
              <Button
                type="button"
                variant="danger"
                onClick={() => setStep("kill")}
                disabled={pending}
              >
                EMERGENCY STOP
              </Button>
            </div>
          )}
          {errorText ? (
            <p className="text-xs text-[var(--danger)]">{errorText}</p>
          ) : null}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Research</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2">
            <Metric label="Status" value={str(research.status, "UNAVAILABLE")} />
            <Metric label="Symbols analyzed" value={str(research.symbols_analyzed, "—")} />
            <Metric label="Eligible universe" value={str(research.eligible_universe, "—")} />
            <Metric label="Active signals" value={str(research.active_signals, "—")} />
            <Metric label="Signal freshness" value={str(research.signal_freshness, "—")} />
            <Metric label="Coverage" value={str(research.coverage_pct, "—")} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Execution</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2">
            <Metric label="Orders today" value={str(execution.orders_today, "0")} />
            <Metric label="Filled" value={str(execution.filled_orders, "0")} />
            <Metric label="Rejected" value={str(execution.rejected_orders, "0")} />
            <Metric label="Blocked" value={str(execution.blocked_orders, "0")} />
            <Metric label="Last execution" value={str(execution.last_execution, "—")} />
            <Metric label="Last order result" value={str(execution.last_order_result, "—")} />
            <Metric label="ENV EXECUTION_ENABLED" value={execution.execution_enabled_env ? "true" : "false"} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Signal execution</CardTitle>
        </CardHeader>
        <CardContent>
          {signals.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">
              No executable BUY/SELL research rows. Research remains advisory.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-xs">
                <thead className="text-[var(--fg-subtle)]">
                  <tr>
                    {[
                      "Symbol",
                      "Dir",
                      "Price",
                      "SL",
                      "TP",
                      "RR",
                      "Score",
                      "Regime",
                      "Size",
                      "Risk",
                      "Status",
                    ].map((h) => (
                      <th key={h} className="py-2 pr-3 font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {signals.map((sig, idx) => (
                    <tr
                      key={`${str(sig.symbol)}${idx}`}
                      className="border-t border-[var(--border)]"
                    >
                      <td className="py-2 pr-3 font-medium text-[var(--fg)]">
                        {str(sig.symbol)}
                      </td>
                      <td className="py-2 pr-3">{str(sig.direction)}</td>
                      <td className="py-2 pr-3">{str(sig.price)}</td>
                      <td className="py-2 pr-3">{str(sig.stop_loss)}</td>
                      <td className="py-2 pr-3">{str(sig.take_profit)}</td>
                      <td className="py-2 pr-3">{str(sig.risk_reward)}</td>
                      <td className="py-2 pr-3">{str(sig.score)}</td>
                      <td className="py-2 pr-3">{str(sig.regime)}</td>
                      <td className="py-2 pr-3">
                        {str(asRecord(sig.position_size).volume, "—")}
                      </td>
                      <td className="py-2 pr-3">{str(sig.estimated_risk)}</td>
                      <td className="py-2 pr-3">
                        <Badge
                          tone={
                            str(sig.execution_status) === "ALLOWED"
                              ? "success"
                              : "warning"
                          }
                        >
                          {str(sig.execution_status, "BLOCKED")}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {signals.map((sig, idx) => {
            const why = str(sig.why_this_signal, "");
            const blocked = asList(sig.why_blocked).map(String);
            if (!why && blocked.length === 0) return null;
            return (
              <div
                key={`why-${idx}`}
                className="mt-3 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs"
              >
                <p className="font-medium text-[var(--fg)]">
                  {str(sig.symbol)} {str(sig.direction)}
                </p>
                {why && why !== "—" ? (
                  <p className="mt-1 text-[var(--fg-muted)]">
                    WHY THIS SIGNAL: {why}
                  </p>
                ) : (
                  <p className="mt-1 text-[var(--fg-subtle)]">
                    WHY THIS SIGNAL: evidence unavailable — not fabricated.
                  </p>
                )}
                {blocked.length ? (
                  <p className="mt-1 text-[var(--warning)]">
                    WHY THIS TRADE WAS BLOCKED: {blocked.join("; ")}
                  </p>
                ) : null}
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}

function StatusTile({
  label,
  value,
  ok,
}: {
  label: string;
  value: string;
  ok: boolean;
}) {
  return (
    <div className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2">
      <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p className="mt-1">
        <Badge tone={connTone(ok)}>{value}</Badge>
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p className="mt-0.5 text-sm text-[var(--fg)]">{value}</p>
    </div>
  );
}

function ConfirmationBlock({
  title,
  confirm,
  broker,
  account,
  risk,
  phrase,
  setPhrase,
  ack,
  setAck,
  phraseOk,
  pending,
  onCancel,
  onConfirm,
  danger,
}: {
  title: string;
  confirm: Record<string, unknown>;
  broker: Record<string, unknown>;
  account: Record<string, unknown>;
  risk: Record<string, unknown>;
  phrase: string;
  setPhrase: (v: string) => void;
  ack: boolean;
  setAck: (v: boolean) => void;
  phraseOk: boolean;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  danger: boolean;
}) {
  const warning = str(
    confirm.warning,
    "Trades use real money. Capital preservation is the priority.",
  );
  return (
    <div className="space-y-3 rounded-[var(--radius-os)] border border-[var(--danger)] bg-[var(--surface-2)] p-4">
      <p className="text-sm font-semibold text-[var(--fg)]">{title}</p>
      <p className="text-xs text-[var(--warning)]">{warning}</p>
      <dl className="grid gap-1 text-xs sm:grid-cols-2">
        <div>
          <dt className="text-[var(--fg-subtle)]">Broker</dt>
          <dd>{str(broker.server)} · {str(broker.login_masked)}</dd>
        </div>
        <div>
          <dt className="text-[var(--fg-subtle)]">Balance / equity</dt>
          <dd>
            {str(account.balance)} / {str(account.equity)}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--fg-subtle)]">Risk / trade</dt>
          <dd>{str(risk.risk_per_trade_pct)}%</dd>
        </div>
        <div>
          <dt className="text-[var(--fg-subtle)]">Daily loss / max positions</dt>
          <dd>
            {str(risk.max_daily_loss_pct)}% / {str(risk.max_open_positions)}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--fg-subtle)]">Open positions</dt>
          <dd>{str(account.open_positions, "0")}</dd>
        </div>
      </dl>
      <label className="flex items-start gap-2 text-xs text-[var(--fg)]">
        <input
          type="checkbox"
          checked={ack}
          onChange={(e) => setAck(e.target.checked)}
        />
        I understand these trades use real money and may lose capital.
      </label>
      <label className="block text-xs text-[var(--fg-muted)]">
        Type {CONFIRM_PHRASE}
        <input
          className="mt-1 w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--fg)]"
          value={phrase}
          onChange={(e) => setPhrase(e.target.value)}
          autoComplete="off"
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant={danger ? "danger" : "default"}
          disabled={!ack || !phraseOk || pending}
          onClick={onConfirm}
        >
          Confirm
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel} disabled={pending}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
