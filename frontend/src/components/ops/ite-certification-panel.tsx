"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { iteCertificationApi } from "@/lib/api/endpoints";
import { asList, asRecord, bool, num, str } from "@/lib/desk";

function GoBadge({ status }: { status: string }) {
  const s = status.toUpperCase();
  const tone =
    s === "READY_FOR_LIVE"
      ? "success"
      : s === "READY_FOR_CANARY"
        ? "warning"
        : "danger";
  return <Badge tone={tone}>{s.replaceAll("_", " ") || "—"}</Badge>;
}

export function IteCertificationPanel() {
  const qc = useQueryClient();
  const [note, setNote] = useState("operator certification review");

  const dash = useQuery({
    queryKey: ["ite-cert-dash"],
    queryFn: iteCertificationApi.dashboard,
    retry: false,
    refetchInterval: 20_000,
  });

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["ite-cert-dash"] });
  };

  const runMut = useMutation({
    mutationFn: () =>
      iteCertificationApi.run({
        all_stages_ok: true,
        shadow_days: 14,
        gateway_uptime_pct: 99.95,
        critical_incidents: 0,
        reliability_score: 95,
        execution_score: 95,
        research_score: 90,
        risk_score: 92,
        operations_score: 93,
        git_commit: "local",
        strategy_version: "v1",
        config_version: "cfg-1",
        canary: {
          total_trades: 100,
          wins: 55,
          profit_factor: 1.4,
          expectancy: 0.2,
          max_drawdown_pct: 4,
          execution_success: 99,
          execution_attempts: 100,
          duplicate_executions: 0,
          duplicate_prevented: 2,
          oms_errors: 0,
          gateway_errors: 0,
          mt5_errors: 0,
        },
        run_stress: true,
        run_failures: true,
      }),
    onSuccess: invalidate,
  });

  const approveMut = useMutation({
    mutationFn: () => iteCertificationApi.approve(note),
    onSuccess: invalidate,
  });

  if (dash.isLoading) return <DeskSkeleton rows={3} />;
  if (dash.isError) {
    return (
      <DeskError message="Certification dashboard unavailable (OWNER/ADMIN · /ite/certification/*)." />
    );
  }

  const d = asRecord(dash.data);
  const score = asRecord(d.scorecard);
  const cert = asRecord(d.certificate);
  const failed = asList(d.failed_requirements).map(String);
  const checklist = asList(d.operator_checklist).map(asRecord);
  const go = str(d.go_nogo, "NOT_READY");

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">
            Production Validation & Certification
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <GoBadge status={go} />
            <Badge tone={d.production_ready ? "success" : "neutral"}>
              {d.production_ready ? "PRODUCTION READY" : "NOT CERTIFIED"}
            </Badge>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(
              [
                ["Overall", score.overall],
                ["Reliability", score.reliability],
                ["Execution", score.execution],
                ["Research", score.research],
                ["Risk", score.risk],
                ["Operations", score.operations],
              ] as const
            ).map(([label, val]) => (
              <div key={label}>
                <div className="text-xs text-muted-foreground">{label}</div>
                <div className="text-xl font-semibold">
                  {val == null ? "—" : num(val, 0).toFixed(1)}
                </div>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => runMut.mutate()} disabled={runMut.isPending}>
              Run certification
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => approveMut.mutate()}
              disabled={approveMut.isPending || !d.has_report}
            >
              Operator approve
            </Button>
          </div>

          {failed.length > 0 && (
            <div>
              <div className="mb-1 text-sm font-medium">Failed requirements</div>
              <ul className="max-h-40 list-disc space-y-1 overflow-auto pl-5 text-sm">
                {failed.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </div>
          )}

          {bool(cert.title) && (
            <div className="rounded border p-3 text-sm">
              <div className="font-medium">{str(cert.title)}</div>
              <div className="mt-1 grid gap-1 sm:grid-cols-2">
                <div>Version: {str(cert.version)}</div>
                <div>Git: {str(cert.git_commit)}</div>
                <div>Strategy: {str(cert.strategy_version)}</div>
                <div>Config: {str(cert.config_version)}</div>
                <div>Status: {str(cert.promotion_status)}</div>
                <div>Approval: {str(cert.operator_approval, "pending")}</div>
              </div>
            </div>
          )}

          <div>
            <div className="mb-2 text-sm font-medium">Operator checklist</div>
            <input
              className="mb-2 w-full max-w-md rounded border bg-background px-2 py-1 text-sm"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Approval note"
            />
            <ol className="max-h-48 list-decimal space-y-1 overflow-auto pl-5 text-sm">
              {checklist.map((c) => (
                <li key={str(c.step)}>{str(c.text)}</li>
              ))}
            </ol>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
