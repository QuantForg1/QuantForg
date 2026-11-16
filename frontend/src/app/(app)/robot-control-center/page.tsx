"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Bot, Pause, Play, Power, ShieldAlert, Square } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { robotControlApi, tradingSessionApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { formatRelativeTime } from "@/lib/utils";
import {
    OWNER_MAX_LOT,
    OWNER_MAX_PLANNED_RISK_PCT,
    OWNER_MAX_SPREAD,
    OWNER_MIN_REWARD_RISK,
    OWNER_SESSION_LABEL,
} from "@/lib/execution/ticket-risk";
import {
    ROBOT_ACTIONS,
    robotStateTone,
    robotStateLabel,
    type RobotAction,
} from "@/lib/trading/robot-control";

const ACTION_ICON: Record<RobotAction, typeof Pause> = {
    pause: Pause,
    resume: Play,
    start: Power,
    stop: Square,
    emergency_stop: ShieldAlert,
};

function errorText(err: unknown): string {
    if (err instanceof ApiError) {
        const d = asRecord(err.details);
        const detail = asRecord(d.detail);
        return str(detail.message, "") || err.message;
    }
    return err instanceof Error ? err.message : "Request failed";
}

export default function RobotControlCenterPage() {
    const qc = useQueryClient();
    const [pending, setPending] = useState<string | null>(null);

    const accountsQ = useQuery({
        queryKey: ["robot-control-accounts"],
        queryFn: robotControlApi.accounts,
        refetchInterval: 15_000,
        retry: false,
    });
    const sessionQ = useQuery({
        queryKey: ["trading-session"],
        queryFn: tradingSessionApi.session,
        refetchInterval: 15_000,
        retry: false,
    });

    const act = useMutation({
        mutationFn: (v: { id: string; action: RobotAction; reason: string }) =>
            robotControlApi.act(v.id, v.action, v.reason),
        onMutate: (v) => setPending(`${v.id}:${v.action}`),
        onSettled: () => setPending(null),
        onSuccess: (res) => {
            // Show what the backend confirmed, never what was clicked.
            toast.success(
                `Robot is now ${robotStateLabel(str(asRecord(res).state, ""))}`,
            );
            void qc.invalidateQueries({ queryKey: ["robot-control-accounts"] });
        },
        onError: (err) => toast.error(errorText(err)),
    });

    const data = asRecord(accountsQ.data);
    const accounts = asList(data.accounts).map(asRecord);
    const events = asList(data.events).map(asRecord);
    const allowed = asRecord(data.actions);
    const session = asRecord(sessionQ.data);
    const autoTrading = str(
        asRecord(session.auto_trading).run_state ??
            session.auto_trading_run_state,
        "unknown",
    );

    function run(id: string, action: RobotAction) {
        let reason = "";
        if (action === "emergency_stop" || action === "start") {
            reason =
                window.prompt(
                    action === "emergency_stop"
                        ? "Reason for the emergency stop (recorded in the audit log):"
                        : "Reason for starting the robot (required after an emergency stop):",
                ) ?? "";
            if (action === "emergency_stop" && !reason.trim()) return;
        }
        act.mutate({ id, action, reason });
    }

    return (
        <div>
            <PageHeader
                eyebrow="Robot"
                title="Robot Control Center"
                description="Control your robot per broker account. Pause and Stop block new entries at the execution boundary; open positions keep their stops and targets and are never closed by these controls."
            />
            <PageMotion className="space-y-4">
                <div className="grid gap-4 md:grid-cols-3">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-sm">
                                Owner risk policy
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-1 text-xs text-[var(--fg-muted)]">
                            <p>
                                Risk per trade ≤ {OWNER_MAX_PLANNED_RISK_PCT}% ·
                                daily stop 25%
                            </p>
                            <p>
                                RR ≥ {OWNER_MIN_REWARD_RISK} after spread ·
                                spread ≤ ${OWNER_MAX_SPREAD}
                            </p>
                            <p>
                                Quality ≥ 75 · lot {OWNER_MAX_LOT} · 1 position
                            </p>
                            <p>
                                {OWNER_SESSION_LABEL} · no martingale, grid or
                                forced trades
                            </p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-sm">
                                Broker session
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-1 text-xs text-[var(--fg-muted)]">
                            <p>
                                Connection:{" "}
                                <Badge
                                    tone={
                                        session.connected
                                            ? "success"
                                            : "warning"
                                    }
                                >
                                    {session.connected
                                        ? "Connected"
                                        : sessionQ.isError
                                          ? "Unavailable"
                                          : "Not connected"}
                                </Badge>
                            </p>
                            <p>
                                Auto-trading run state (bound account):{" "}
                                {autoTrading}
                            </p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-sm">
                                How controls work
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-1 text-xs text-[var(--fg-muted)]">
                            <p>
                                Resume and Start re-check MT5 trade permission
                                first.
                            </p>
                            <p>
                                Each account is independent; nothing here
                                affects other users.
                            </p>
                        </CardContent>
                    </Card>
                </div>

                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-sm">
                            <Bot className="h-4 w-4" /> Your accounts
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {accountsQ.isLoading ? (
                            <p className="text-xs text-[var(--fg-muted)]">
                                Loading…
                            </p>
                        ) : accountsQ.isError ? (
                            <p className="text-xs text-[var(--danger)]">
                                Robot state could not be loaded. New entries
                                stay blocked until it can be read.
                            </p>
                        ) : accounts.length === 0 ? (
                            <p className="text-xs text-[var(--fg-muted)]">
                                No broker accounts yet. Connect one in Broker
                                Accounts.
                            </p>
                        ) : (
                            <div className="divide-y divide-[var(--border)]">
                                {accounts.map((a) => {
                                    const id = str(a.broker_account_id, "");
                                    const state = str(a.robot_state, "RUNNING");
                                    return (
                                        <div
                                            key={id}
                                            className="flex flex-wrap items-center gap-3 py-3"
                                        >
                                            <div className="min-w-[220px] flex-1">
                                                <p className="text-sm font-medium">
                                                    {str(a.broker, "Broker")} ·{" "}
                                                    {str(a.login_masked, "")}
                                                </p>
                                                <p className="text-xs text-[var(--fg-muted)]">
                                                    {str(a.server, "")} ·{" "}
                                                    {str(a.environment, "")} ·
                                                    trade allowed:{" "}
                                                    {str(
                                                        a.trade_allowed_reported,
                                                        "unknown",
                                                    )}
                                                </p>
                                            </div>
                                            <Badge tone={robotStateTone(state)}>
                                                {robotStateLabel(state)}
                                            </Badge>
                                            <div className="flex flex-wrap gap-2">
                                                {ROBOT_ACTIONS.filter((act) =>
                                                    asList(allowed[act])
                                                        .map(String)
                                                        .includes(state),
                                                ).map((action) => {
                                                    const Icon =
                                                        ACTION_ICON[action];
                                                    return (
                                                        <Button
                                                            key={action}
                                                            size="sm"
                                                            variant={
                                                                action ===
                                                                "emergency_stop"
                                                                    ? "danger"
                                                                    : "secondary"
                                                            }
                                                            disabled={
                                                                pending !== null
                                                            }
                                                            onClick={() =>
                                                                run(id, action)
                                                            }
                                                        >
                                                            <Icon className="mr-1 h-3.5 w-3.5" />
                                                            {pending ===
                                                            `${id}:${action}`
                                                                ? "…"
                                                                : robotActionLabel(
                                                                      action,
                                                                  )}
                                                        </Button>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="text-sm">
                            Control history
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {events.length === 0 ? (
                            <p className="text-xs text-[var(--fg-muted)]">
                                No control actions yet.
                            </p>
                        ) : (
                            <ul className="space-y-1 text-xs">
                                {events.map((e, i) => (
                                    <li
                                        key={i}
                                        className="flex flex-wrap gap-2 text-[var(--fg-muted)]"
                                    >
                                        <span className="tabular">
                                            {formatRelativeTime(str(e.at, ""))}
                                        </span>
                                        <span className="font-medium text-[var(--fg)]">
                                            {str(e.action, "")}
                                        </span>
                                        <span>
                                            {robotStateLabel(
                                                str(e.state_before, ""),
                                            )}{" "}
                                            →{" "}
                                            {robotStateLabel(
                                                str(e.state_after, ""),
                                            )}
                                        </span>
                                        {str(e.reason, "") ? (
                                            <span>· {str(e.reason, "")}</span>
                                        ) : null}
                                    </li>
                                ))}
                            </ul>
                        )}
                    </CardContent>
                </Card>
            </PageMotion>
        </div>
    );
}

function robotActionLabel(action: RobotAction): string {
    return {
        pause: "Pause",
        resume: "Resume",
        start: "Start",
        stop: "Stop",
        emergency_stop: "Emergency stop",
    }[action];
}
