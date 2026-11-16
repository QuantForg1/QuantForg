"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Activity,
  Bot,
  CircleAlert,
  Cpu,
  History,
  LineChart,
  Pause,
  Play,
  Power,
  ShieldAlert,
  SlidersHorizontal,
  Square,
  Wallet,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

function SectionTitle({
  icon: Icon,
  children,
}: {
  icon: typeof Bot;
  children: React.ReactNode;
}) {
  return (
    <CardTitle className="flex items-center gap-2 text-sm">
      <Icon className="h-4 w-4 text-[var(--accent)]" aria-hidden />
      {children}
    </CardTitle>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 text-xs">
      <span className="text-[var(--fg-muted)]">{label}</span>
      <span className="text-right font-medium text-[var(--fg)]">{value}</span>
    </div>
  );
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

  const accountsQ = useQuery({
    queryKey: ["robot-control-accounts"],
    queryFn: robotControlApi.accounts,
    refetchInterval: 15_000,
    retry: 1,
  });

  const data = asRecord(accountsQ.data);
  const accounts = asList(data.accounts).map(asRecord);
  const events = asList(data.events).map(asRecord);
  const activity = asList(data.activity).map(asRecord);
  const allowed = asRecord(data.actions);
  const strategy = asRecord(data.strategy);
  const evidence = str(data.broker_evidence, "");
  const subscription = data.subscription_active;

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
    onError: (err) => toast.error(errorText(err)),
  });

  const accountName = (id: string) => {
    const a = accounts.find((x) => str(x.broker_account_id, "") === id);
    return a ? `${str(a.broker, "Broker")} ${str(a.login_masked, "")}` : "";
  };

  return (
    <div>
      <PageHeader
        eyebrow="Robot"
        title="Robot Control Center"
        description="Your robot, per broker account. Controls never close open positions; every action is checked and recorded on the server."
      />
      <PageMotion className="space-y-4">
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

        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <Card>
              <CardHeader>
                <SectionTitle icon={Bot}>Your robot</SectionTitle>
              </CardHeader>
              <CardContent>
                {accountsQ.isLoading ? (
                  <div className="space-y-3" aria-busy>
                    <Skeleton className="h-20 w-full" />
                    <Skeleton className="h-20 w-full" />
                  </div>
                ) : accountsQ.isError ? (
                  <div className="space-y-2 text-xs">
                    <p className="text-[var(--danger)]">
                      Robot state could not be loaded ({errorText(accountsQ.error)}).
                      New entries stay blocked until it can be read.
                    </p>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => void accountsQ.refetch()}
                    >
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
                  <ul className="space-y-3">
                    {accounts.map((a) => {
                      const id = str(a.broker_account_id, "");
                      const control = str(a.robot_state, "");
                      const status = asRecord(a.status);
                      const conn = asRecord(a.connection);
                      const worker = asRecord(a.worker);
                      const actions = ROBOT_ACTIONS.filter((x) =>
                        asList(allowed[x]).map(String).includes(control),
                      );
                      return (
                        <li
                          key={id}
                          className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-3"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold">
                                {str(a.broker, "Broker")} · {str(a.login_masked, "")}
                              </p>
                              <p className="truncate text-xs text-[var(--fg-muted)]">
                                {str(a.server, "")} · {str(a.environment, "") || "—"}
                              </p>
                            </div>
                            <Badge tone={robotStatusTone(str(status.code, ""))}>
                              {str(status.label, "Status not confirmed")}
                            </Badge>
                          </div>
                          <div className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
                            <div>
                              <p className="text-[var(--fg-muted)]">Broker connection</p>
                              <Badge
                                className="mt-1"
                                tone={connectionStateTone(str(conn.state, ""))}
                                title={str(conn.detail, "")}
                              >
                                {connectionStateLabel(str(conn.state, ""))}
                              </Badge>
                            </div>
                            <div>
                              <p className="text-[var(--fg-muted)]">Robot control</p>
                              <p className="mt-1 font-medium">
                                {robotStateLabel(control)}
                              </p>
                            </div>
                            <div>
                              <p className="text-[var(--fg-muted)]">Trading terminal</p>
                              <p className="mt-1 font-medium">
                                {str(conn.source, "") === "gateway"
                                  ? "Platform terminal"
                                  : worker.assigned
                                    ? worker.connected
                                      ? "Assigned · online"
                                      : "Assigned · offline"
                                    : "Waiting for a terminal"}
                              </p>
                            </div>
                          </div>
                          {str(conn.detail, "") ? (
                            <p className="mt-2 text-xs text-[var(--warning)]">
                              {str(conn.detail, "")}
                            </p>
                          ) : null}
                          <div className="mt-3 flex flex-wrap gap-2">
                            {actions.length === 0 ? (
                              <p className="text-xs text-[var(--fg-muted)]">
                                No control is available in this state.
                              </p>
                            ) : (
                              actions.map((action) => {
                                const Icon = ACTION_ICON[action];
                                return (
                                  <Button
                                    key={action}
                                    size="sm"
                                    className="min-h-9"
                                    variant={
                                      action === "emergency_stop"
                                        ? "danger"
                                        : "secondary"
                                    }
                                    title={ACTION_HELP[action]}
                                    disabled={pending !== null}
                                    onClick={() => {
                                      setReason("");
                                      setConfirm({
                                        id,
                                        action,
                                        label: `${str(a.broker, "Broker")} ${str(a.login_masked, "")}`,
                                      });
                                    }}
                                  >
                                    <Icon className="h-3.5 w-3.5" />
                                    {pending === `${id}:${action}`
                                      ? "Working…"
                                      : robotActionLabel(action)}
                                  </Button>
                                );
                              })
                            )}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </CardContent>
            </Card>

            <PositionsCard />

            <Card>
              <CardHeader>
                <SectionTitle icon={Activity}>Recent execution activity</SectionTitle>
              </CardHeader>
              <CardContent>
                {accountsQ.isLoading ? (
                  <Skeleton className="h-16 w-full" />
                ) : activity.length === 0 ? (
                  <p className="text-xs text-[var(--fg-muted)]">
                    No robot orders yet. Each attempt, including ones blocked by
                    risk checks, appears here.
                  </p>
                ) : (
                  <ul className="divide-y divide-[var(--border)] text-xs">
                    {activity.map((e, i) => (
                      <li
                        key={i}
                        className="flex flex-wrap items-center justify-between gap-2 py-2"
                      >
                        <span className="font-medium">
                          {[str(e.side, ""), str(e.symbol, ""), str(e.volume, "")]
                            .filter(Boolean)
                            .join(" ") || "Order"}
                          <span className="ml-2 text-[var(--fg-muted)]">
                            {accountName(str(e.broker_account_id, ""))}
                          </span>
                        </span>
                        <span className="flex items-center gap-2">
                          <Badge
                            tone={
                              str(e.outcome, "") === "Executed"
                                ? "success"
                                : str(e.outcome, "").startsWith("Blocked")
                                  ? "warning"
                                  : "neutral"
                            }
                          >
                            {str(e.outcome, "Recorded")}
                          </Badge>
                          <span className="tabular text-[var(--fg-muted)]">
                            {formatRelativeTime(str(e.at, ""))}
                          </span>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <SectionTitle icon={History}>Control history</SectionTitle>
              </CardHeader>
              <CardContent>
                {events.length === 0 ? (
                  <p className="text-xs text-[var(--fg-muted)]">
                    No control actions yet.
                  </p>
                ) : (
                  <ul className="divide-y divide-[var(--border)] text-xs">
                    {events.map((e, i) => (
                      <li key={i} className="flex flex-wrap gap-x-3 gap-y-1 py-2">
                        <span className="tabular text-[var(--fg-muted)]">
                          {formatRelativeTime(str(e.at, ""))}
                        </span>
                        <span className="font-medium">
                          {robotActionLabel(str(e.action, "") as RobotAction) ||
                            str(e.action, "")}
                        </span>
                        <span className="text-[var(--fg-muted)]">
                          {robotStateLabel(str(e.state_before, ""))} →{" "}
                          {robotStateLabel(str(e.state_after, ""))}
                        </span>
                        <span className="text-[var(--fg-muted)]">
                          {accountName(str(e.broker_account_id, ""))}
                        </span>
                        {str(e.reason, "") ? (
                          <span className="w-full text-[var(--fg-muted)] sm:w-auto">
                            “{str(e.reason, "")}”
                          </span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="space-y-4">
            <Card>
              <CardHeader>
                <SectionTitle icon={LineChart}>Strategy</SectionTitle>
              </CardHeader>
              <CardContent>
                {accountsQ.isLoading ? (
                  <Skeleton className="h-14 w-full" />
                ) : (
                  <div className="divide-y divide-[var(--border)]">
                    <Row label="Strategy" value={str(strategy.name, "—")} />
                    <Row
                      label="Instruments"
                      value={asList(strategy.instruments).map(String).join(", ") || "—"}
                    />
                    <Row label="Style" value={str(strategy.style, "—")} />
                  </div>
                )}
              </CardContent>
            </Card>

            <RiskSettingsCard />

            <Card>
              <CardHeader>
                <SectionTitle icon={Cpu}>Health</SectionTitle>
              </CardHeader>
              <CardContent className="divide-y divide-[var(--border)]">
                <Row
                  label="Broker data"
                  value={
                    accountsQ.isLoading ? (
                      "Checking…"
                    ) : evidence === "complete" ? (
                      <Badge tone="success">Available</Badge>
                    ) : evidence === "unavailable" ? (
                      <Badge tone="warning">Unavailable</Badge>
                    ) : (
                      <Badge>Unknown</Badge>
                    )
                  }
                />
                <Row
                  label="Subscription"
                  value={
                    subscription === true ? (
                      <Badge tone="success">Active</Badge>
                    ) : subscription === false ? (
                      <Link className="text-[var(--accent)] underline" href="/pricing">
                        Inactive · renew
                      </Link>
                    ) : (
                      <Badge>Unknown</Badge>
                    )
                  }
                />
                <Row
                  label="Last update"
                  value={
                    accountsQ.dataUpdatedAt
                      ? formatRelativeTime(new Date(accountsQ.dataUpdatedAt).toISOString())
                      : "—"
                  }
                />
              </CardContent>
            </Card>
          </div>
        </div>
      </PageMotion>

      <Dialog open={confirm !== null} onOpenChange={(o) => !o && setConfirm(null)}>
        <DialogContent className="w-[min(94vw,440px)]">
          {confirm ? (
            <form
              className="space-y-3"
              onSubmit={(ev) => {
                ev.preventDefault();
                if (confirm.action === "emergency_stop" && !reason.trim()) return;
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
    <Card>
      <CardHeader>
        <SectionTitle icon={Wallet}>Open positions</SectionTitle>
      </CardHeader>
      <CardContent>
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
      </CardContent>
    </Card>
  );
}

function RiskSettingsCard() {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["risk-preferences"],
    queryFn: riskApi.preferences,
    retry: 1,
  });
  const payload = asRecord(q.data);
  const prefs = asRecord(payload.preferences);
  const fields = useMemo(
    () => editableRiskFields(asRecord(payload.bounds)),
    [payload.bounds],
  );
  const [draft, setDraft] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!q.data) return;
    const next: Record<string, string> = {};
    for (const f of fields) next[f.key] = trimNumber(str(prefs[f.key], ""));
    setDraft(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.data]);

  const save = useMutation({
    mutationFn: () =>
      riskApi.updatePreferences({
        planned_risk_pct: draft.planned_risk_pct ?? str(prefs.planned_risk_pct, ""),
        aggregate_open_risk_pct:
          draft.aggregate_open_risk_pct ?? str(prefs.aggregate_open_risk_pct, ""),
        max_lot: draft.max_lot ?? str(prefs.max_lot, ""),
        daily_loss_pct: draft.daily_loss_pct ?? str(prefs.daily_loss_pct, ""),
        max_concurrent_positions: Number(
          draft.max_concurrent_positions ?? prefs.max_concurrent_positions ?? 1,
        ),
      }),
    onSuccess: () => {
      toast.success("Risk settings saved");
      void qc.invalidateQueries({ queryKey: ["risk-preferences"] });
    },
    onError: (err) => toast.error(errorText(err)),
  });

  const dirty = fields.some(
    (f) => (draft[f.key] ?? "") !== trimNumber(str(prefs[f.key], "")),
  );

  return (
    <Card>
      <CardHeader>
        <SectionTitle icon={SlidersHorizontal}>Your risk settings</SectionTitle>
      </CardHeader>
      <CardContent>
        {q.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : q.isError ? (
          <p className="text-xs text-[var(--danger)]">
            Risk settings could not be loaded.
          </p>
        ) : (
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              save.mutate();
            }}
          >
            {fields.map((f) => (
              <div key={f.key} className="space-y-1">
                <Label htmlFor={`risk-${f.key}`} className="text-xs">
                  {f.label}
                </Label>
                <div className="flex items-center gap-2">
                  <Input
                    id={`risk-${f.key}`}
                    inputMode="decimal"
                    value={draft[f.key] ?? ""}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, [f.key]: e.target.value }))
                    }
                    className="h-9"
                  />
                  <span className="w-6 text-xs text-[var(--fg-muted)]">
                    {f.unit === "percent" ? "%" : ""}
                  </span>
                </div>
                <p className="text-[11px] text-[var(--fg-muted)]">{f.help}</p>
              </div>
            ))}
            <p className="text-[11px] text-[var(--fg-muted)]">
              The server validates every change. The platform&apos;s own
              protections always apply, and the stricter limit wins.
            </p>
            <Button type="submit" size="sm" disabled={!dirty || save.isPending}>
              {save.isPending ? "Saving…" : "Save settings"}
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  );
}

/** "9.0000" -> "9"; leaves non-numeric text untouched. */
function trimNumber(raw: string): string {
  const n = Number(raw);
  return raw.trim() !== "" && Number.isFinite(n) ? String(n) : raw;
}
