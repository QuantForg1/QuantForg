"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Activity,
  Bot,
  CircleAlert,
  Database,
  FileText,
  Heart,
  Info,
  Link2,
  Minus,
  Monitor,
  Pause,
  Play,
  Plus,
  Power,
  Shield,
  ShieldAlert,
  Square,
  Wallet,
  Wifi,
} from "lucide-react";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { portfolioApi, riskApi, robotControlApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { formatRelativeTime } from "@/lib/utils";
import {
  connectionStateLabel,
  connectionStateTone,
  editableRiskFields,
  ROBOT_ACTIONS,
  robotActionLabel,
  robotStateLabel,
  robotStatusTone,
  type RobotAction,
} from "@/lib/trading/robot-control";

const ACTION_ICON: Record<RobotAction, typeof Pause> = {
  pause: Pause,
  resume: Play,
  start: Power,
  stop: Square,
  emergency_stop: ShieldAlert,
};

const ACTION_HELP: Record<RobotAction, string> = {
  pause: "Blocks new entries. Open positions keep their stop-loss and target.",
  resume:
    "Re-checks account ownership, MT5 trading permission, terminal health, risk and subscription first.",
  start:
    "Re-checks every requirement before the robot may trade again.",
  stop: "Stops automated activity. Open positions are not closed.",
  emergency_stop:
    "Immediately blocks all new entries for this account and records the reason.",
};

function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    const d = asRecord(err.details);
    const detail = asRecord(d.detail);
    return str(detail.message, "") || err.message;
  }
  return err instanceof Error ? err.message : "Request failed";
}

function isSubscriptionRequired(err: unknown): boolean {
  if (!(err instanceof ApiError)) return false;
  if (err.status === 402) return true;
  const detail = asRecord(asRecord(err.details).detail);
  return str(detail.code, err.code ?? "") === "subscription_required";
}

function StatusDot({
  tone,
}: {
  tone: "success" | "warning" | "danger" | "neutral";
}) {
  const color =
    tone === "success"
      ? "bg-[var(--success)]"
      : tone === "warning"
        ? "bg-[var(--warning)]"
        : tone === "danger"
          ? "bg-[var(--danger)]"
          : "bg-[var(--fg-subtle)]";
  return (
    <span className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${color}`} aria-hidden />
  );
}

function nudgeDraft(raw: string, direction: 1 | -1, unit: string): string {
  const current = Number(raw);
  const base = Number.isFinite(current) ? current : 0;
  const delta = unit === "lots" ? 0.01 : unit === "count" ? 1 : 0.5;
  const digits = unit === "lots" ? 2 : unit === "count" ? 0 : 1;
  const next = base + direction * delta;
  const floored = next < 0 ? 0 : next;
  if (digits === 0) return String(Math.round(floored));
  return floored.toFixed(digits).replace(/0+$/, "").replace(/\.$/, "");
}

function connectionQuality(account: Record<string, unknown> | null): {
  label: string;
  tone: "success" | "warning" | "danger" | "neutral";
} {
  if (!account) return { label: "Unknown", tone: "neutral" };
  const worker = asRecord(account.worker);
  if (worker.connected === true) return { label: "Online", tone: "success" };
  if (worker.assigned === true) return { label: "Offline", tone: "warning" };
  const state = str(asRecord(account.connection).state, "");
  if (state === "ROBOT_READY" || state === "CONNECTED") return { label: "Online", tone: "success" };
  if (state === "DEGRADED") return { label: "Degraded", tone: "warning" };
  if (state === "NOT_CONNECTED" || state === "UNAVAILABLE") return { label: "Offline", tone: "neutral" };
  return { label: "Unknown", tone: "neutral" };
}

export default function RobotControlCenterPage() {
  const qc = useQueryClient();
  const [pending, setPending] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{
    id: string;
    action: RobotAction;
    label: string;
  } | null>(null);
  const [reason, setReason] = useState("");
  const [subscribeOpen, setSubscribeOpen] = useState(false);

  const accountsQ = useQuery({
    queryKey: ["robot-control-accounts"],
    queryFn: robotControlApi.accounts,
    refetchInterval: 15_000,
    retry: 1,
  });

  const data = asRecord(accountsQ.data);
  const accounts = asList(data.accounts).map(asRecord);
  const allowed = asRecord(data.actions);
  const evidence = str(data.broker_evidence, "");

  const act = useMutation({
    mutationFn: (v: { id: string; action: RobotAction; reason: string }) =>
      robotControlApi.act(v.id, v.action, v.reason),
    onMutate: (v) => setPending(`${v.id}:${v.action}`),
    onSettled: () => setPending(null),
    onSuccess: (res) => {
      // Report what the backend confirmed, never what was clicked.
      toast.success(
        `Robot control is now ${robotStateLabel(str(asRecord(res).state, ""))}`,
      );
      void qc.invalidateQueries({ queryKey: ["robot-control-accounts"] });
    },
    onError: (err) => {
      if (isSubscriptionRequired(err)) {
        setSubscribeOpen(true);
        return;
      }
      toast.error(errorText(err));
    },
  });
  const subscriptionInactive = data.subscription_active === false;

  const primary = accounts[0] ?? null;
  const primaryStatus = asRecord(primary?.status);
  const primaryConn = asRecord(primary?.connection);
  const quality = connectionQuality(primary);
  const kpis: Array<{
    label: string;
    value: string;
    tone: "success" | "warning" | "danger" | "neutral";
    icon: typeof Activity;
  }> = [
    {
      label: "Operating state",
      value: accountsQ.isLoading
        ? "Checking"
        : accountsQ.isError
          ? "Unavailable"
          : accounts.length === 0
            ? "No account"
            : str(primaryStatus.label, "Status not confirmed"),
      tone: accountsQ.isError
        ? "danger"
        : accountsQ.isLoading
          ? "neutral"
          : robotStatusTone(str(primaryStatus.code, "")),
      icon: Activity,
    },
    {
      label: "Broker status",
      value: accountsQ.isLoading
        ? "Checking"
        : accountsQ.isError
          ? "Unavailable"
          : accounts.length === 0
            ? "Disconnected"
            : connectionStateLabel(str(primaryConn.state, "")),
      tone: accountsQ.isError
        ? "danger"
        : accountsQ.isLoading
          ? "neutral"
          : connectionStateTone(str(primaryConn.state, "")),
      icon: Link2,
    },
    {
      label: "Broker data",
      value: accountsQ.isLoading
        ? "Checking"
        : evidence === "complete"
          ? "Available"
          : evidence === "unavailable"
            ? "Unavailable"
            : "Unknown",
      tone: evidence === "complete" ? "success" : evidence === "unavailable" ? "warning" : "neutral",
      icon: Database,
    },
    {
      label: "Connection",
      value: accountsQ.isLoading ? "Checking" : accountsQ.isError ? "Unavailable" : quality.label,
      tone: accountsQ.isLoading || accountsQ.isError ? "neutral" : quality.tone,
      icon: Shield,
    },
  ];

  return (
    <div className="qf-overview relative min-w-0 space-y-4">
      <header className="qf-overview-enter relative overflow-hidden">
        <svg className="qf-overview-wave" viewBox="0 0 480 120" fill="none" aria-hidden>
          <path d="M0 78C78 78 118 22 198 42s128 52 282-8" stroke="currentColor" strokeWidth="2.2" />
          <path d="M0 96C104 96 168 46 246 60s132 42 234-6" stroke="currentColor" strokeWidth="1.6" opacity="0.65" />
        </svg>
        <div className="relative z-[1] flex items-start gap-3">
          <span className="mt-1 h-6 w-1 shrink-0 rounded-full bg-[var(--accent)]" aria-hidden />
          <div className="min-w-0">
            <h1 className="text-base font-semibold tracking-tight text-[var(--fg)] sm:text-lg">
              Monitor your robot, broker connection, and risk settings
            </h1>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-[var(--fg-muted)] sm:text-sm">
              Status comes from the server for each broker account. Controls never close open positions.
            </p>
          </div>
        </div>
      </header>

      {subscriptionInactive ? (
        <div
          role="status"
          data-testid="rcc-subscription-required"
          className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-os)] border border-[color-mix(in_srgb,var(--warning)_45%,var(--border))] bg-[color-mix(in_srgb,var(--warning)_8%,transparent)] px-4 py-3"
        >
          <p className="text-sm text-[var(--fg)]">
            <span className="font-semibold">Subscription required.</span>{" "}
            <span className="text-[var(--fg-muted)]">
              Your broker stays connected and verified. Choose a plan to let the robot trade.
            </span>
          </p>
          <Link
            href="/pricing"
            className="qf-btn-primary inline-flex h-9 items-center rounded-[var(--radius-sm)] px-4 text-sm font-semibold"
          >
            View plans
          </Link>
        </div>
      ) : null}
      <PageMotion className="space-y-4">
        <section
          aria-label="Robot operating summary"
          className="grid grid-cols-2 items-stretch gap-2 sm:gap-3 xl:grid-cols-4"
        >
          {kpis.map((item, index) => {
            const Icon = item.icon;
            return (
              <article
                key={item.label}
                className="qf-overview-card qf-overview-enter flex h-full min-h-[5.25rem] min-w-0 items-center gap-2.5 px-3 py-3 sm:gap-3 sm:px-4"
                style={{ animationDelay: `${index * 40}ms` }}
              >
                <span className="qf-overview-icon qf-overview-icon-sm" aria-hidden>
                  <Icon className="h-4 w-4" />
                </span>
                <div className="min-w-0">
                  <p className="truncate text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                    {item.label}
                  </p>
                  <p className="mt-1 flex items-center gap-1.5 truncate text-sm font-semibold text-[var(--fg)]">
                    <StatusDot tone={item.tone} />
                    {item.value}
                  </p>
                </div>
              </article>
            );
          })}
        </section>
        {evidence === "unavailable" ? (
          <div
            role="status"
            className="flex items-start gap-2 rounded-[var(--radius-os)] border border-[var(--warning)] bg-[var(--warning-soft)] px-3 py-2 text-xs text-[var(--fg)]"
          >
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-[var(--warning)]" />
            <span>
              Broker data is temporarily unavailable. New entries stay blocked
              until it can be read again. Your controls and settings still
              work.
            </span>
          </div>
        ) : null}

        <div className="grid items-stretch gap-4 lg:grid-cols-2">
          <section
            className="qf-overview-panel qf-overview-enter order-1 flex min-w-0 flex-col self-stretch overflow-hidden lg:order-2"
            style={{ animationDelay: "80ms" }}
            aria-labelledby="your-robot"
          >
            <div className="flex items-center justify-between gap-3 border-b border-[color-mix(in_srgb,var(--accent)_16%,var(--border))] px-4 py-3">
              <h2 id="your-robot" className="flex items-center gap-2 text-sm font-semibold">
                <span className="qf-overview-icon qf-overview-icon-sm" aria-hidden>
                  <Bot className="h-4 w-4" />
                </span>
                Your robot
              </h2>
            </div>
            <div className="flex min-h-0 flex-1 flex-col p-3 sm:p-4">
              {accountsQ.isLoading ? (
                <div className="space-y-3" aria-busy>
                  <Skeleton className="h-20 w-full" />
                  <Skeleton className="h-28 w-full" />
                </div>
              ) : accountsQ.isError ? (
                <div className="space-y-2 text-xs">
                  <p className="text-[var(--danger)]">
                    Robot state could not be loaded ({errorText(accountsQ.error)}).
                    New entries stay blocked until it can be read.
                  </p>
                  <Button size="sm" variant="secondary" onClick={() => void accountsQ.refetch()}>
                    Retry
                  </Button>
                </div>
              ) : accounts.length === 0 ? (
                <div className="space-y-2 text-xs text-[var(--fg-muted)]">
                  <p>No broker account is connected yet.</p>
                  <Button asChild size="sm">
                    <Link href="/broker">Connect a broker account</Link>
                  </Button>
                </div>
              ) : (
                <ul className="flex flex-1 flex-col gap-4">
                  {accounts.map((a) => {
                    const id = str(a.broker_account_id, "");
                    const control = str(a.robot_state, "");
                    const status = asRecord(a.status);
                    const conn = asRecord(a.connection);
                    const worker = asRecord(a.worker);
                    const actions = ROBOT_ACTIONS.filter((x) =>
                      asList(allowed[x]).map(String).includes(control),
                    );
                    const lead =
                      (["pause", "resume", "start"] as RobotAction[]).find((action) =>
                        actions.includes(action),
                      ) ?? "pause";
                    const slots: RobotAction[] = [lead, "stop", "emergency_stop"];
                    const tiles: Array<{ icon: typeof Wifi; label: string; value: string }> = [
                      {
                        icon: Wifi,
                        label: "Broker connection",
                        value: connectionStateLabel(str(conn.state, "")),
                      },
                      {
                        icon: Play,
                        label: "Robot control",
                        value: robotStateLabel(control),
                      },
                      {
                        icon: Monitor,
                        label: "Trading terminal",
                        value:
                          str(conn.source, "") === "gateway"
                            ? "Platform gateway"
                            : worker.assigned
                              ? worker.connected
                                ? "MT5 worker online"
                                : "MT5 worker offline"
                              : "Waiting for a terminal",
                      },
                      {
                        icon: Heart,
                        label: "Heartbeat",
                        value: str(worker.heartbeat_at, "")
                          ? formatRelativeTime(str(worker.heartbeat_at, ""))
                          : "Not supplied",
                      },
                      { icon: Activity, label: "Market condition", value: "Not supplied" },
                      { icon: FileText, label: "Decision text", value: "Not supplied" },
                    ];
                    return (
                      <li key={id} className="flex min-h-0 flex-1 flex-col">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                          <img
                            src="/brand/quantforg-mark.png"
                            alt=""
                            width={72}
                            height={72}
                            className="h-16 w-16 shrink-0 rounded-2xl border border-[color-mix(in_srgb,var(--accent)_28%,var(--border))] bg-[var(--surface-2)] object-contain p-1.5 shadow-[var(--shadow-card)]"
                          />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-base font-semibold">
                              {str(a.broker, "Broker")} {str(a.login_masked, "")}
                            </p>
                            <p className="truncate text-xs text-[var(--fg-muted)]">
                              {str(a.server, "") || "—"}
                              {str(a.environment, "") ? ` · ${str(a.environment, "")}` : ""}
                            </p>
                          </div>
                          <Badge tone={robotStatusTone(str(status.code, ""))}>
                            {str(status.label, "Status not confirmed")}
                          </Badge>
                        </div>
                        <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                          {tiles.map((tile) => {
                            const Icon = tile.icon;
                            return (
                              <div
                                key={tile.label}
                                className="flex min-w-0 items-center gap-2.5 rounded-[var(--radius-os)] border border-[color-mix(in_srgb,var(--accent)_14%,var(--border))] bg-[color-mix(in_srgb,var(--bg)_28%,transparent)] px-3 py-2.5"
                              >
                                <Icon className="h-4 w-4 shrink-0 text-[var(--accent)]" aria-hidden />
                                <div className="min-w-0">
                                  <p className="text-[10px] uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
                                    {tile.label}
                                  </p>
                                  <p className="truncate text-sm font-medium text-[var(--fg)]">{tile.value}</p>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                        {str(conn.detail, "") ? (
                          <p className="mt-2 text-xs text-[var(--warning)]">{str(conn.detail, "")}</p>
                        ) : null}
                        <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-3">
                          {slots.map((action) => {
                            const Icon = ACTION_ICON[action];
                            const enabled = actions.includes(action);
                            return (
                              <Button
                                key={action}
                                size="sm"
                                className="min-h-11 w-full"
                                variant={action === "emergency_stop" ? "danger" : "secondary"}
                                title={ACTION_HELP[action]}
                                disabled={!enabled || pending !== null}
                                onClick={() => {
                                  if (!enabled) return;
                                  setReason("");
                                  setConfirm({
                                    id,
                                    action,
                                    label: `${str(a.broker, "Broker")} ${str(a.login_masked, "")}`,
                                  });
                                }}
                              >
                                <Icon className="h-3.5 w-3.5" />
                                {pending === `${id}:${action}` ? "Working…" : robotActionLabel(action)}
                              </Button>
                            );
                          })}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </section>
          <RiskSettingsCard />
        </div>
        <PositionsCard />
      </PageMotion>

      <Dialog open={subscribeOpen} onOpenChange={setSubscribeOpen}>
        <DialogContent className="w-[min(94vw,460px)]" data-testid="rcc-activate-robot">
          <DialogTitle>Activate Your QuantForg Robot</DialogTitle>
          <p className="text-sm text-[var(--fg-muted)]">
            Your broker has been successfully connected and verified. To activate automated
            trading, choose a subscription plan.
          </p>
          <p className="text-sm text-[var(--fg-muted)]">
            Your broker connection and account information will remain saved. No trades will be
            executed until your subscription is active and all trading requirements are
            satisfied.
          </p>
          <div className="flex justify-end gap-2">
            <DialogClose asChild>
              <Button type="button" variant="ghost">
                Not now
              </Button>
            </DialogClose>
            <Link
              href="/pricing"
              className="qf-btn-primary inline-flex h-10 items-center rounded-[var(--radius-sm)] px-4 text-sm font-semibold"
            >
              Continue to Plans
            </Link>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={confirm !== null} onOpenChange={(o) => !o && setConfirm(null)}>
        <DialogContent className="w-[min(94vw,440px)]">
          {confirm ? (
            <form
              className="space-y-3"
              onSubmit={(ev) => {
                ev.preventDefault();
                if (confirm.action === "emergency_stop" && !reason.trim()) return;
                if (
                  subscriptionInactive &&
                  (confirm.action === "start" || confirm.action === "resume")
                ) {
                  setConfirm(null);
                  setSubscribeOpen(true);
                  return;
                }
                act.mutate({ id: confirm.id, action: confirm.action, reason });
                setConfirm(null);
              }}
            >
              <DialogTitle>
                {robotActionLabel(confirm.action)} · {confirm.label}
              </DialogTitle>
              <p className="text-xs text-[var(--fg-muted)]">
                {ACTION_HELP[confirm.action]}
              </p>
              <div className="space-y-1">
                <Label htmlFor="rcc-reason">
                  Reason{confirm.action === "emergency_stop" ? " (required)" : " (optional)"}
                </Label>
                <Input
                  id="rcc-reason"
                  value={reason}
                  maxLength={300}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Recorded in your control history"
                />
              </div>
              <div className="flex justify-end gap-2">
                <DialogClose asChild>
                  <Button type="button" variant="ghost">
                    Cancel
                  </Button>
                </DialogClose>
                <Button
                  type="submit"
                  variant={confirm.action === "emergency_stop" ? "danger" : "default"}
                  disabled={confirm.action === "emergency_stop" && !reason.trim()}
                >
                  Confirm
                </Button>
              </div>
            </form>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function PositionsCard() {
  const q = useQuery({
    queryKey: ["rcc-positions"],
    queryFn: () => portfolioApi.positions(),
    refetchInterval: 20_000,
    retry: false,
  });
  const rows = Array.isArray(q.data) ? q.data.map(asRecord) : [];
  const status = q.error instanceof ApiError ? q.error.status : 0;
  return (
    <section className="qf-overview-panel qf-overview-enter overflow-hidden" aria-labelledby="open-positions">
      <div className="flex items-center gap-2 border-b border-[color-mix(in_srgb,var(--accent)_16%,var(--border))] px-4 py-3">
        <span className="qf-overview-icon qf-overview-icon-sm" aria-hidden>
          <Wallet className="h-4 w-4" />
        </span>
        <h2 id="open-positions" className="text-sm font-semibold">
          Open positions
        </h2>
      </div>
      <div className="p-3 sm:p-4">
        {q.isLoading ? (
          <Skeleton className="h-12 w-full" />
        ) : q.isError ? (
          <p className="text-xs text-[var(--fg-muted)]">
            {status === 404
              ? "Live position monitoring appears here once your account runs on a QuantForg trading terminal."
              : status === 503
                ? "Broker data is temporarily unavailable; positions cannot be read right now."
                : "Positions could not be loaded."}
          </p>
        ) : rows.length === 0 ? (
          <p className="text-xs text-[var(--fg-muted)]">No open positions.</p>
        ) : (
          <div className="-mx-1 overflow-x-auto">
            <table className="w-full min-w-[420px] text-xs">
              <thead className="text-left text-[var(--fg-muted)]">
                <tr>
                  <th className="px-1 py-1 font-medium">Symbol</th>
                  <th className="px-1 py-1 font-medium">Side</th>
                  <th className="px-1 py-1 text-right font-medium">Volume</th>
                  <th className="px-1 py-1 text-right font-medium">Stop</th>
                  <th className="px-1 py-1 text-right font-medium">Target</th>
                  <th className="px-1 py-1 text-right font-medium">P/L</th>
                </tr>
              </thead>
              <tbody className="tabular">
                {rows.map((p, i) => {
                  const pnl = Number(p.profit ?? p.pnl ?? 0);
                  return (
                    <tr key={i} className="border-t border-[var(--border)]">
                      <td className="px-1 py-1.5">{str(p.symbol, "")}</td>
                      <td className="px-1 py-1.5">{str(p.side ?? p.type, "").toUpperCase()}</td>
                      <td className="px-1 py-1.5 text-right">{str(p.volume, "")}</td>
                      <td className="px-1 py-1.5 text-right">{str(p.stop_loss ?? p.sl, "—")}</td>
                      <td className="px-1 py-1.5 text-right">{str(p.take_profit ?? p.tp, "—")}</td>
                      <td
                        className={`px-1 py-1.5 text-right ${pnl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}`}
                      >
                        {Number.isFinite(pnl) ? pnl.toFixed(2) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

const PERIOD_LIMITS = [
  {
    key: "weekly_loss_pct",
    label: "Weekly loss limit",
    unit: "percent",
    help: "Loss this week at which new entries stop. 0 turns it off.",
  },
  {
    key: "monthly_loss_pct",
    label: "Monthly loss limit",
    unit: "percent",
    help: "Loss this month at which new entries stop. 0 turns it off.",
  },
  {
    key: "max_drawdown_pct",
    label: "Maximum drawdown halt",
    unit: "percent",
    help: "Drop from the equity high at which new entries stop. 0 turns it off.",
  },
] as const;

function RiskSettingsCard() {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["risk-preferences"],
    queryFn: riskApi.preferences,
    retry: 1,
  });
  const profileQ = useQuery({
    queryKey: ["risk-profile"],
    queryFn: () => riskApi.profile(),
    retry: 1,
  });
  const payload = asRecord(q.data);
  const prefs = asRecord(payload.preferences);
  const profile = asRecord(profileQ.data);
  const effective = asRecord(profile.effective);
  const fields = useMemo(
    () => editableRiskFields(asRecord(payload.bounds)),
    [payload.bounds],
  );
  // Period limits are only editable when the profile really loaded: a failed
  // load must never be shown (or saved) as 0 = "limit off".
  const periodLoaded = profileQ.isSuccess && Object.keys(effective).length > 0;
  const rows = [
    ...fields,
    ...(periodLoaded ? PERIOD_LIMITS.map((field) => ({ ...field })) : []),
  ];
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [periodBaseline, setPeriodBaseline] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!q.data && !profileQ.data) return;
    const next: Record<string, string> = {};
    for (const f of fields) next[f.key] = trimNumber(str(prefs[f.key], ""));
    const base: Record<string, string> = {};
    if (periodLoaded) {
      for (const f of PERIOD_LIMITS) {
        base[f.key] = trimNumber(str(effective[f.key], "0")) || "0";
        next[f.key] = base[f.key];
      }
    }
    setPeriodBaseline(base);
    setDraft(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.data, profileQ.data]);

  const prefDirty = fields.some(
    (f) => (draft[f.key] ?? "") !== trimNumber(str(prefs[f.key], "")),
  );
  const periodDirty =
    periodLoaded &&
    PERIOD_LIMITS.some(
      (f) => f.key in periodBaseline && (draft[f.key] ?? "") !== periodBaseline[f.key],
    );
  const dirty = prefDirty || periodDirty;

  const save = useMutation({
    mutationFn: async () => {
      if (prefDirty) {
        await riskApi.updatePreferences({
          planned_risk_pct: draft.planned_risk_pct ?? str(prefs.planned_risk_pct, ""),
          aggregate_open_risk_pct:
            draft.aggregate_open_risk_pct ?? str(prefs.aggregate_open_risk_pct, ""),
          max_lot: draft.max_lot ?? str(prefs.max_lot, ""),
          daily_loss_pct: draft.daily_loss_pct ?? str(prefs.daily_loss_pct, ""),
          max_concurrent_positions: Number(
            draft.max_concurrent_positions ?? prefs.max_concurrent_positions ?? 1,
          ),
        });
      }
      if (periodDirty) {
        const fresh = asRecord(await riskApi.profile());
        const changes: Record<string, string> = {};
        // Send only what the customer edited; untouched limits keep their
        // server value even if it changed meanwhile.
        for (const field of PERIOD_LIMITS) {
          if (!(field.key in periodBaseline)) continue;
          const next = (draft[field.key] ?? "").trim();
          if (next === "" || next === periodBaseline[field.key]) continue;
          changes[field.key] = next;
        }
        if (Object.keys(changes).length > 0) {
          await riskApi.updateProfile({
            changes,
            expected_version: Number(fresh.version ?? 0),
          });
        }
      }
    },
    onSuccess: () => {
      toast.success("Risk settings saved");
      void qc.invalidateQueries({ queryKey: ["risk-preferences"] });
      void qc.invalidateQueries({ queryKey: ["risk-profile"] });
    },
    onError: (err) => toast.error(errorText(err)),
  });

  return (
    <section
      className="qf-overview-panel qf-overview-enter order-2 flex min-w-0 flex-col self-stretch lg:order-1"
      style={{ animationDelay: "120ms" }}
      aria-labelledby="risk-settings"
    >
      <div className="flex items-center gap-2 border-b border-[color-mix(in_srgb,var(--accent)_16%,var(--border))] px-4 py-3">
        <span className="qf-overview-icon qf-overview-icon-sm" aria-hidden>
          <Shield className="h-4 w-4" />
        </span>
        <h2 id="risk-settings" className="text-sm font-semibold">
          Your risk settings
        </h2>
      </div>
      <div className="flex flex-1 flex-col p-3 sm:p-4">
        {q.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : q.isError ? (
          <p className="text-xs text-[var(--danger)]">
            Risk settings could not be loaded.
          </p>
        ) : (
          <form
            className="flex flex-1 flex-col gap-1"
            onSubmit={(e) => {
              e.preventDefault();
              save.mutate();
            }}
          >
            {rows.map((f) => (
              <div key={f.key} className="flex flex-col gap-2 border-b border-[var(--border)] py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between">
                <Label htmlFor={`risk-${f.key}`} className="flex items-center gap-1.5 text-sm font-medium">
                  {f.label}
                  <span title={f.help} className="text-[var(--fg-subtle)]">
                    <Info className="h-3.5 w-3.5" aria-hidden />
                    <span className="sr-only">{f.help}</span>
                  </span>
                </Label>
                <div className="flex h-10 items-center gap-1 self-start rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-1 sm:self-auto">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-8 w-8 px-0"
                    aria-label={`Decrease ${f.label}`}
                    onClick={() =>
                      setDraft((d) => ({
                        ...d,
                        [f.key]: nudgeDraft(d[f.key] ?? "", -1, f.unit),
                      }))
                    }
                  >
                    <Minus className="h-3.5 w-3.5" />
                  </Button>
                  <Input
                    id={`risk-${f.key}`}
                    inputMode="decimal"
                    value={draft[f.key] ?? ""}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, [f.key]: e.target.value }))
                    }
                    className="h-8 w-16 border-0 bg-transparent px-1 text-center shadow-none focus-visible:ring-0"
                  />
                  <span className="w-4 text-xs text-[var(--fg-muted)]">
                    {f.unit === "percent" ? "%" : ""}
                  </span>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-8 w-8 px-0"
                    aria-label={`Increase ${f.label}`}
                    onClick={() =>
                      setDraft((d) => ({
                        ...d,
                        [f.key]: nudgeDraft(d[f.key] ?? "", 1, f.unit),
                      }))
                    }
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}
            {!periodLoaded ? (
              <p className="py-2 text-xs text-[var(--fg-muted)]">
                {profileQ.isLoading
                  ? "Loading weekly, monthly and drawdown limits…"
                  : "Weekly, monthly and drawdown limits are unavailable right now. They are unchanged and still enforced."}
              </p>
            ) : null}
            <div className="mt-auto pt-3">
              <Button type="submit" className="min-h-11 w-full" disabled={!dirty || save.isPending}>
                {save.isPending ? "Saving…" : "Save settings"}
              </Button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}

/** "9.0000" -> "9"; leaves non-numeric text untouched. */
function trimNumber(raw: string): string {
  const n = Number(raw);
  return raw.trim() !== "" && Number.isFinite(n) ? String(n) : raw;
}
