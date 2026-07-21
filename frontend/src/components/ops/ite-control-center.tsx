"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";

function ModeBadge({ mode }: { mode: string }) {
  const m = mode.toUpperCase();
  const tone =
    m === "LIVE" ? "success" : m === "CANARY" ? "warning" : "neutral";
  return <Badge tone={tone}>{m || "—"}</Badge>;
}

export function IteControlCenter() {
  const qc = useQueryClient();
  const [reason, setReason] = useState("operator action");
  const [confirm, setConfirm] = useState(false);
  const [rollbackTarget, setRollbackTarget] = useState("");
  const [runbookId, setRunbookId] = useState("start_of_trading_day");
  const [checklist, setChecklist] = useState<
    Array<{ step: number; text: string; done: boolean }>
  >([]);

  const center = useQuery({
    queryKey: ["ite-ops-center"],
    queryFn: iteOpsApi.controlCenter,
    retry: false,
    refetchInterval: 15_000,
  });
  const readiness = useQuery({
    queryKey: ["ite-ops-readiness"],
    queryFn: iteOpsApi.readiness,
    retry: false,
    refetchInterval: 15_000,
  });
  const alerts = useQuery({
    queryKey: ["ite-ops-alerts"],
    queryFn: () => iteOpsApi.alerts(true),
    retry: false,
    refetchInterval: 15_000,
  });
  const configs = useQuery({
    queryKey: ["ite-ops-configs"],
    queryFn: iteOpsApi.configs,
    retry: false,
  });
  const runbooks = useQuery({
    queryKey: ["ite-ops-runbooks"],
    queryFn: iteOpsApi.runbooks,
    retry: false,
  });

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["ite-ops-center"] });
    void qc.invalidateQueries({ queryKey: ["ite-ops-readiness"] });
    void qc.invalidateQueries({ queryKey: ["ite-ops-alerts"] });
    void qc.invalidateQueries({ queryKey: ["ite-ops-configs"] });
  };

  const modeMut = useMutation({
    mutationFn: (target: string) => iteOpsApi.setMode(target, reason, confirm),
    onSuccess: invalidate,
  });
  const killMut = useMutation({
    mutationFn: (arm: boolean) =>
      arm
        ? iteOpsApi.armKill(reason, confirm)
        : iteOpsApi.disarmKill(reason, confirm),
    onSuccess: invalidate,
  });
  const rollbackMut = useMutation({
    mutationFn: () => iteOpsApi.rollback(rollbackTarget, reason, confirm),
    onSuccess: invalidate,
  });
  const ackMut = useMutation({
    mutationFn: (id: string) => iteOpsApi.ackAlert(id),
    onSuccess: invalidate,
  });
  const runbookMut = useMutation({
    mutationFn: (id: string) => iteOpsApi.executeRunbook(id),
    onSuccess: (data) => {
      const rows = asList(asRecord(data).checklist).map(asRecord);
      setChecklist(
        rows.map((r) => ({
          step: Number(r.step) || 0,
          text: str(r.text),
          done: Boolean(r.done),
        })),
      );
    },
  });

  const cc = asRecord(center.data);
  const rd = asRecord(readiness.data);
  const alertRows = asList(asRecord(alerts.data).alerts).map(asRecord);
  const versionRows = asList(asRecord(configs.data).versions).map(asRecord);
  const runbookRows = asList(asRecord(runbooks.data).runbooks).map(asRecord);

  const nextMode = useMemo(() => {
    const m = str(cc.execution_mode).toUpperCase();
    if (m === "SHADOW") return "CANARY";
    if (m === "CANARY") return "LIVE";
    if (m === "LIVE") return "SHADOW";
    return "CANARY";
  }, [cc.execution_mode]);

  if (center.isLoading) return <DeskSkeleton rows={4} />;
  if (center.isError) {
    return (
      <DeskError message="ITE Control Center unavailable — OWNER/ADMIN required (/ite/ops/*)." />
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">
            Institutional Operations Control Center
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <div className="text-xs text-muted-foreground">System</div>
              <div className="font-medium">{str(cc.system_status, "—")}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Gateway</div>
              <div className="font-medium">{str(cc.gateway_status, "—")}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">MT5</div>
              <div className="font-medium">{str(cc.mt5_status, "—")}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Mode</div>
              <ModeBadge mode={str(cc.execution_mode)} />
              <p className="mt-1 text-[10px] text-muted-foreground">
                SHADOW → CANARY → LIVE. Canary: 0.01 lot · max 1 position · fail-closed halt.
                LIVE is operator-only.
              </p>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Kill switch</div>
              <Badge tone={cc.kill_switch ? "danger" : "neutral"}>
                {cc.kill_switch ? "ARMED" : "DISARMED"}
              </Badge>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Strategy</div>
              <div className="font-mono text-sm">{str(cc.strategy_version)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Config</div>
              <div className="font-mono text-sm">{str(cc.config_version)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Git</div>
              <div className="font-mono text-sm">{str(cc.git_commit, "—")}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Promotion</div>
              <div className="font-medium">{str(cc.promotion_status)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Health score</div>
              <div className="font-medium">{str(rd.health_score, "0")}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Shadow / Canary / Live</div>
              <div className="flex gap-1 pt-1">
                <Badge tone={cc.shadow_mode ? "accent" : "neutral"}>S</Badge>
                <Badge tone={cc.canary_mode ? "warning" : "neutral"}>C</Badge>
                <Badge tone={cc.live_mode ? "success" : "neutral"}>L</Badge>
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">OMS / PME</div>
              <div className="text-sm">
                orders {cc.oms_orders_allowed ? "on" : "off"} · pme{" "}
                {cc.pme_modifications_allowed ? "on" : "off"}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-end gap-2 border-t pt-3">
            <label className="text-xs">
              Reason
              <input
                className="ml-2 rounded border bg-background px-2 py-1 text-sm"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={confirm}
                onChange={(e) => setConfirm(e.target.checked)}
              />
              Confirm
            </label>
            <Button
              size="sm"
              disabled={!confirm || modeMut.isPending}
              onClick={() => modeMut.mutate(nextMode)}
            >
              Transition → {nextMode}
            </Button>
            <Button
              size="sm"
              variant="danger"
              disabled={!confirm || killMut.isPending}
              onClick={() => killMut.mutate(true)}
            >
              Arm kill switch
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!confirm || killMut.isPending}
              onClick={() => killMut.mutate(false)}
            >
              Disarm kill switch
            </Button>
          </div>

          <div className="flex flex-wrap items-end gap-2">
            <label className="text-xs">
              Rollback target
              <select
                className="ml-2 rounded border bg-background px-2 py-1 text-sm"
                value={rollbackTarget}
                onChange={(e) => setRollbackTarget(e.target.value)}
              >
                <option value="">Select config…</option>
                {versionRows.map((v) => (
                  <option key={str(v.id)} value={str(v.config_version)}>
                    {str(v.config_version)} ({str(v.strategy_version)})
                  </option>
                ))}
              </select>
            </label>
            <Button
              size="sm"
              variant="secondary"
              disabled={!confirm || !rollbackTarget || rollbackMut.isPending}
              onClick={() => rollbackMut.mutate()}
            >
              One-click rollback
            </Button>
          </div>

          {(modeMut.isError || killMut.isError || rollbackMut.isError) && (
            <p className="text-sm text-destructive">
              Action failed — check confirmation, permissions, and transition rules.
            </p>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Unacked alerts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {alertRows.length === 0 && (
              <p className="text-sm text-muted-foreground">No unacknowledged alerts.</p>
            )}
            {alertRows.map((a) => (
              <div
                key={str(a.id)}
                className="flex items-center justify-between gap-2 rounded border px-2 py-1 text-sm"
              >
                <span>
                  <Badge tone="neutral">{str(a.severity)}</Badge> {str(a.message)}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => ackMut.mutate(str(a.id))}
                >
                  Ack
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Production runbooks</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <select
                className="rounded border bg-background px-2 py-1 text-sm"
                value={runbookId}
                onChange={(e) => setRunbookId(e.target.value)}
              >
                {runbookRows.map((r) => (
                  <option key={str(r.id)} value={str(r.id)}>
                    {str(r.title)}
                  </option>
                ))}
              </select>
              <Button
                size="sm"
                onClick={() => runbookMut.mutate(runbookId)}
                disabled={runbookMut.isPending}
              >
                Open checklist
              </Button>
            </div>
            <ol className="list-decimal space-y-1 pl-5 text-sm">
              {checklist.map((s) => (
                <li key={s.step}>{s.text}</li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Production readiness</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 sm:grid-cols-3 lg:grid-cols-4 text-sm">
          {[
            ["Research", str(rd.research_status)],
            ["Promotion", str(rd.promotion_status)],
            ["Execution", str(rd.execution_status)],
            ["Risk", str(rd.risk_status)],
            ["Gateway", str(rd.gateway)],
            ["MT5", str(rd.mt5)],
            ["Mode", str(rd.current_mode)],
            ["Strategy", str(rd.current_strategy)],
            ["Config", str(rd.current_config)],
            ["Health", str(rd.health_score)],
          ].map(([k, v]) => (
            <div key={k}>
              <div className="text-xs text-muted-foreground">{k}</div>
              <div className="font-medium">{v || "—"}</div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
