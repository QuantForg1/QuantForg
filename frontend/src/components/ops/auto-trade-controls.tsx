"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";

const SESSION_OPTIONS = [
  "london",
  "new_york",
  "london_ny_overlap",
  "tokyo",
  "sydney",
] as const;

export function AutoTradeControls() {
  const qc = useQueryClient();
  const [reason, setReason] = useState("operator auto-trade update");
  const [confirm, setConfirm] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [maxOpen, setMaxOpen] = useState("1");
  const [riskPct, setRiskPct] = useState("1.0");
  const [dailyLoss, setDailyLoss] = useState("3.0");
  const [maxSpread, setMaxSpread] = useState("2.00");
  const [symbols, setSymbols] = useState("XAUUSD");
  const [sessions, setSessions] = useState<string[]>([
    "london",
    "new_york",
    "london_ny_overlap",
  ]);
  const [newsFilter, setNewsFilter] = useState(false);

  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 15_000,
  });

  useEffect(() => {
    if (!autoQ.data) return;
    const d = asRecord(autoQ.data);
    const policy = asRecord(d.policy);
    setEnabled(Boolean(policy.enabled));
    setMaxOpen(str(policy.max_open_positions, "1"));
    setRiskPct(str(policy.risk_per_trade_pct, "1.0"));
    setDailyLoss(str(policy.max_daily_loss_pct, "3.0"));
    setMaxSpread(str(policy.max_spread, "2.00"));
    setSymbols(asList(policy.allowed_symbols).map(String).join(", ") || "XAUUSD");
    setSessions(
      asList(policy.allowed_sessions).map(String).length
        ? asList(policy.allowed_sessions).map(String)
        : ["london", "new_york", "london_ny_overlap"],
    );
    setNewsFilter(Boolean(policy.news_filter_enabled));
  }, [autoQ.data]);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["ite-ops-auto-trading"] });
    void qc.invalidateQueries({ queryKey: ["ite-ops-center"] });
    void qc.invalidateQueries({ queryKey: ["ite-ops-readiness"] });
  };

  const saveMut = useMutation({
    mutationFn: () =>
      iteOpsApi.updateAutoTrading({
        reason,
        confirmed: confirm,
        enabled,
        max_open_positions: Number(maxOpen) || 1,
        risk_per_trade_pct: riskPct,
        max_daily_loss_pct: dailyLoss,
        max_spread: maxSpread,
        allowed_symbols: symbols
          .split(",")
          .map((s) => s.trim().toUpperCase())
          .filter(Boolean),
        allowed_sessions: sessions,
        news_filter_enabled: newsFilter,
      }),
    onSuccess: invalidate,
  });

  const stopMut = useMutation({
    mutationFn: () => iteOpsApi.emergencyStop(reason || "emergency stop", confirm),
    onSuccess: invalidate,
  });

  if (autoQ.isLoading) return <DeskSkeleton rows={3} />;
  if (autoQ.isError) {
    return (
      <DeskError message="Auto Trading controls unavailable — OWNER/ADMIN required." />
    );
  }

  const d = asRecord(autoQ.data);
  const status = str(d.status, "Disabled");
  const failed = asList(d.failed_reasons).map(String);
  const conditions = asList(d.conditions).map(asRecord);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          Auto Trade Controls
          <Badge tone={status === "Enabled" ? "success" : "warning"}>
            {status}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {failed.length > 0 && (
          <div className="rounded border border-[var(--border)] bg-[var(--surface-2)] p-3 text-sm">
            <div className="mb-1 text-xs text-muted-foreground">
              Auto Trading Disabled — exact reasons
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

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            Auto Trading ON/OFF
          </label>
          <label className="text-xs">
            Max open positions
            <input
              className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm"
              value={maxOpen}
              onChange={(e) => setMaxOpen(e.target.value)}
            />
          </label>
          <label className="text-xs">
            Risk per trade (%)
            <input
              className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm"
              value={riskPct}
              onChange={(e) => setRiskPct(e.target.value)}
            />
          </label>
          <label className="text-xs">
            Maximum daily loss (%)
            <input
              className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm"
              value={dailyLoss}
              onChange={(e) => setDailyLoss(e.target.value)}
            />
          </label>
          <label className="text-xs">
            Maximum spread
            <input
              className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm"
              value={maxSpread}
              onChange={(e) => setMaxSpread(e.target.value)}
            />
          </label>
          <label className="text-xs">
            Allowed symbols
            <input
              className="mt-1 w-full rounded border bg-background px-2 py-1 text-sm"
              value={symbols}
              onChange={(e) => setSymbols(e.target.value)}
            />
          </label>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input
              type="checkbox"
              checked={newsFilter}
              onChange={(e) => setNewsFilter(e.target.checked)}
            />
            News filter ON/OFF
          </label>
        </div>

        <fieldset className="space-y-2">
          <legend className="text-xs text-muted-foreground">
            Allowed trading sessions
          </legend>
          <div className="flex flex-wrap gap-3">
            {SESSION_OPTIONS.map((s) => (
              <label key={s} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={sessions.includes(s)}
                  onChange={(e) => {
                    setSessions((prev) =>
                      e.target.checked
                        ? [...prev, s]
                        : prev.filter((x) => x !== s),
                    );
                  }}
                />
                {s}
              </label>
            ))}
          </div>
        </fieldset>

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
            disabled={!confirm || saveMut.isPending}
            onClick={() => saveMut.mutate()}
          >
            Save controls
          </Button>
          <Button
            size="sm"
            variant="danger"
            disabled={!confirm || stopMut.isPending}
            onClick={() => stopMut.mutate()}
          >
            Emergency STOP
          </Button>
        </div>

        {(saveMut.isError || stopMut.isError) && (
          <p className="text-sm text-destructive">
            Action failed — check confirmation and OWNER/ADMIN permissions.
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          Risk Engine, margin, exposure, daily loss, and drawdown protection are never
          bypassed. Auto Trading stays Disabled until every safety condition PASSes.
        </p>
      </CardContent>
    </Card>
  );
}
