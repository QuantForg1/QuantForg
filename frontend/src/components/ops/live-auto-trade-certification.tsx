"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";

/**
 * Live Auto Trading certification status — display only.
 * Never fabricates trades. Never enables Auto Trading.
 */
export function LiveAutoTradeCertificationPanel() {
  const q = useQuery({
    queryKey: ["ite-ops-live-certification"],
    queryFn: iteOpsApi.liveCertification,
    retry: false,
    refetchInterval: 15_000,
  });

  if (q.isLoading) return <DeskSkeleton rows={3} />;
  if (q.isError) {
    return (
      <DeskError message="Live certification probe unavailable — OWNER/ADMIN required." />
    );
  }

  const d = asRecord(q.data);
  const checklist = asRecord(d.checklist);
  const ready = Boolean(checklist.ready);
  const failed = asList(checklist.failed_reasons).map(String);
  const conditions = asList(checklist.conditions).map(asRecord);
  const last = d.last_report ? asRecord(d.last_report) : null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          Live Auto Trading Certification
          <Badge tone={ready ? "success" : "danger"}>
            {ready ? "READY TO ATTEMPT DEMO" : "STOPPED"}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Demo first (0.01 lot, max 1 position). SHADOW→LIVE is operator-only.
          Auto Trading and Execution Enabled must be explicitly enabled by the
          operator. This panel never sends orders and never fabricates fills.
        </p>

        <div className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <div className="text-xs text-muted-foreground">Ops mode</div>
            <div className="font-medium">{str(d.ops_mode, "—")}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Gateway configured</div>
            <div className="font-medium">
              {d.mt5_gateway_configured ? "yes" : "no"}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Execution Enabled</div>
            <div className="font-medium">{d.execution_enabled ? "yes" : "no"}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Auto Trading</div>
            <div className="font-medium">
              {d.auto_trading_enabled ? "ON" : "OFF"}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Demo volume</div>
            <div className="font-mono">{str(d.demo_volume, "0.01")}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Can attempt broker trade</div>
            <div className="font-medium">
              {d.can_attempt_broker_trade ? "yes" : "no"}
            </div>
          </div>
        </div>

        {!ready && failed.length > 0 && (
          <div className="rounded border border-[var(--border)] bg-[var(--surface-2)] p-3 text-sm">
            <div className="mb-1 text-xs text-muted-foreground">
              STOP — exact reasons
            </div>
            <ul className="list-disc space-y-1 pl-5">
              {failed.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 text-sm">
          {conditions.map((c) => (
            <div
              key={str(c.key)}
              className="flex items-center justify-between gap-2 rounded border px-2 py-1"
            >
              <span>{str(c.label)}</span>
              <Badge tone={c.passed ? "success" : "danger"}>
                {c.passed ? "PASS" : "FAIL"}
              </Badge>
            </div>
          ))}
        </div>

        {last && (
          <div className="rounded border px-3 py-2 text-sm">
            <div className="text-xs text-muted-foreground">Last report</div>
            <div>
              Status{" "}
              <Badge tone={last.certified ? "success" : "warning"}>
                {str(last.status)}
              </Badge>
              {last.failure_reason ? ` — ${str(last.failure_reason)}` : ""}
            </div>
            {last.trade ? (
              <div className="mt-1 font-mono text-xs">
                ticket {str(asRecord(last.trade).ticket)} · deal{" "}
                {str(asRecord(last.trade).deal)} ·{" "}
                {str(asRecord(last.trade).symbol)}{" "}
                {str(asRecord(last.trade).volume)}
              </div>
            ) : (
              <div className="mt-1 text-xs text-muted-foreground">
                No real broker trade evidence on file.
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
