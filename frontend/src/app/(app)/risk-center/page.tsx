"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { RiskIntelligencePanel } from "@/components/trading/dashboard-intelligence/risk-intelligence-panel";
import { RiskRulesPanel } from "@/components/execution/risk-rules-panel";
import { riskApi } from "@/lib/api/endpoints";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { ApiError } from "@/lib/api/client";
import { useTradingSession } from "@/providers/trading-session-provider";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";

const checkSchema = z.object({
  symbol: z.string().min(1),
  side: z.enum(["buy", "sell"]),
  volume: z.string().min(1),
  entry_price: z.string().optional(),
  stop_distance: z.string().optional(),
  risk_pct: z.string().optional(),
});

type PrefForm = {
  planned_risk_pct: string;
  aggregate_open_risk_pct: string;
  max_lot: string;
  daily_loss_pct: string;
  max_concurrent_positions: string;
};

const PREF_KEYS: Array<keyof PrefForm> = [
  "planned_risk_pct",
  "aggregate_open_risk_pct",
  "max_lot",
  "daily_loss_pct",
  "max_concurrent_positions",
];

export default function RiskCenterPage() {
  const session = useTradingSession();
  const qc = useQueryClient();
  const [lastRisk, setLastRisk] = useState<Record<string, unknown> | null>(null);
  const [formValues, setFormValues] = useState<PrefForm>({
    planned_risk_pct: "",
    aggregate_open_risk_pct: "",
    max_lot: "",
    daily_loss_pct: "",
    max_concurrent_positions: "",
  });
  const [baseline, setBaseline] = useState<PrefForm | null>(null);

  const prefsQ = useQuery({
    queryKey: ["risk-preferences"],
    queryFn: () => riskApi.preferences(),
    retry: false,
    staleTime: 15_000,
  });
  const historyQ = useQuery({
    queryKey: ["risk-preference-history"],
    queryFn: () => riskApi.preferenceHistory(40),
    retry: false,
    staleTime: 30_000,
  });

  const prefs = asRecord(prefsQ.data);
  const preferenceBody = asRecord(prefs.preferences);
  const bounds = asRecord(prefs.bounds);
  const effective = asRecord(prefs.effective);
  const protections = asList(prefs.protections).map(asRecord);
  const historyPayload = asRecord(historyQ.data);
  const historyItems = asList(historyPayload.items).map(asRecord);

  useEffect(() => {
    if (!prefsQ.isSuccess) return;
    const next: PrefForm = {
      planned_risk_pct: str(preferenceBody.planned_risk_pct, ""),
      aggregate_open_risk_pct: str(preferenceBody.aggregate_open_risk_pct, ""),
      max_lot: str(preferenceBody.max_lot, ""),
      daily_loss_pct: str(preferenceBody.daily_loss_pct, ""),
      max_concurrent_positions: str(preferenceBody.max_concurrent_positions, ""),
    };
    setFormValues(next);
    setBaseline(next);
  }, [prefsQ.isSuccess, prefsQ.dataUpdatedAt]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty =
    baseline != null &&
    PREF_KEYS.some((key) => formValues[key] !== baseline[key]);

  const saveMut = useMutation({
    mutationFn: () =>
      riskApi.updatePreferences({
        planned_risk_pct: formValues.planned_risk_pct,
        aggregate_open_risk_pct: formValues.aggregate_open_risk_pct,
        max_lot: formValues.max_lot,
        daily_loss_pct: formValues.daily_loss_pct,
        max_concurrent_positions: Number(formValues.max_concurrent_positions),
      }),
    onSuccess: async () => {
      toast.success("Risk preferences saved");
      await qc.invalidateQueries({ queryKey: ["risk-preferences"] });
      await qc.invalidateQueries({ queryKey: ["risk-preference-history"] });
    },
    onError: (e) =>
      toast.error(
        e instanceof ApiError ? e.message : "Could not save risk preferences",
      ),
  });

  const checkForm = useForm<z.infer<typeof checkSchema>>({
    resolver: zodResolver(checkSchema),
    defaultValues: {
      symbol: TRADING_SYMBOL,
      side: "buy",
      volume: "0.01",
      entry_price: "",
      stop_distance: "",
      risk_pct: "1",
    },
  });

  const equity = num(session.equity);
  const free = num(session.freeMargin);
  const floating = num(session.profit);
  const todayPnl = num(session.profit);

  const dailyLossHaltPercent = num(effective.daily_loss_pct);
  const maxAggregateOpenRiskPercent = num(effective.aggregate_open_risk_pct);
  const maxConcurrentPositions = num(effective.max_concurrent_positions);
  const riskPerTradePercent = num(effective.planned_risk_pct);

  return (
    <div>
      <PageHeader
        title="Risk Center"
        description="Monitor your account risk and manage personal preferences within platform-allowed ranges. Global hard limits stay under Owner control."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/inbox">Notifications</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/ai-robot">Robot desk</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/positions">Positions</Link>
            </Button>
          </div>
        }
      />

      <PageMotion className="space-y-4">
        <RiskIntelligencePanel
          equity={session.equity}
          balance={session.balance}
          floatingPnl={floating}
          todayPnl={todayPnl}
          openPositionCount={session.positions.length}
          riskLocked={undefined}
          emergencyStop={undefined}
          liveAuthorization={undefined}
          ordersMaySubmit={undefined}
          showRiskCenterLink={false}
          dailyLossHaltPercent={
            Number.isFinite(dailyLossHaltPercent) ? dailyLossHaltPercent : undefined
          }
          maxAggregateOpenRiskPercent={
            Number.isFinite(maxAggregateOpenRiskPercent)
              ? maxAggregateOpenRiskPercent
              : undefined
          }
          maxConcurrentPositions={
            Number.isFinite(maxConcurrentPositions)
              ? maxConcurrentPositions
              : undefined
          }
          riskPerTradePercent={
            Number.isFinite(riskPerTradePercent) ? riskPerTradePercent : undefined
          }
        />

        <section
          aria-label="Account balances"
          className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
        >
          {(
            [
              [
                "Account equity",
                Number.isFinite(equity) ? formatCurrency(equity) : "—",
              ],
              [
                "Free margin",
                Number.isFinite(free) ? formatCurrency(free) : "—",
              ],
              [
                "Daily P&L",
                Number.isFinite(todayPnl) ? formatCurrency(todayPnl) : "—",
              ],
              [
                "Floating P&L",
                Number.isFinite(floating) ? formatCurrency(floating) : "—",
              ],
            ] as const
          ).map(([label, value]) => (
            <article
              key={label}
              className="flex min-h-[5.5rem] flex-col justify-between rounded-[var(--radius-os)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] p-4 shadow-[var(--shadow-card)]"
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                {label}
              </p>
              <p className="mt-2 text-xl font-semibold tabular tracking-tight text-[var(--fg)]">
                {value}
              </p>
            </article>
          ))}
        </section>

        <Card>
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>My Risk Preferences</CardTitle>
              <p className="mt-1 text-xs text-[var(--fg-muted)]">
                Personal values only. Saves are validated server-side against
                platform hard ceilings and never mutate Owner policy.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {prefs.updated_at ? (
                <span className="text-xs text-[var(--fg-subtle)]">
                  Updated {formatRelativeTime(String(prefs.updated_at))}
                </span>
              ) : null}
              <Badge tone={dirty ? "warning" : "neutral"}>
                {dirty ? "Unsaved changes" : "Saved"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {prefsQ.isError ? (
              <p className="text-sm text-[var(--danger)]">
                Preferences could not be loaded. Retry later — defaults are not
                invented here.
              </p>
            ) : prefsQ.isLoading ? (
              <p className="text-sm text-[var(--fg-muted)]">Loading preferences…</p>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {PREF_KEYS.map((key) => {
                  const bound = asRecord(bounds[key]);
                  const min = str(bound.min, "");
                  const max = str(bound.max, "");
                  const label = str(bound.label, key);
                  const help = str(bound.help, "");
                  return (
                    <div key={key} className="space-y-1.5">
                      <Label htmlFor={`pref-${key}`}>{label}</Label>
                      <Input
                        id={`pref-${key}`}
                        value={formValues[key]}
                        onChange={(e) =>
                          setFormValues((prev) => ({
                            ...prev,
                            [key]: e.target.value,
                          }))
                        }
                        inputMode="decimal"
                      />
                      <p className="text-[11px] text-[var(--fg-subtle)]">
                        Allowed range {min || "—"} – {max || "—"}. {help}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={!dirty || saveMut.isPending || prefsQ.isLoading}
                onClick={() => saveMut.mutate()}
              >
                {saveMut.isPending ? "Saving…" : "Save preferences"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                disabled={!dirty || saveMut.isPending}
                onClick={() => baseline && setFormValues(baseline)}
              >
                Discard
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Risk Protection Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(protections.length
              ? protections
              : [
                  {
                    title: "Protections unavailable",
                    detail:
                      "Protection copy could not be loaded for this session.",
                  },
                ]
            ).map((row) => (
              <div
                key={str(row.id, str(row.title))}
                className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg)]/35 px-3 py-2.5"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium text-[var(--fg)]">
                    {str(row.title)}
                  </p>
                  <Badge tone="success">Enforced</Badge>
                </div>
                <p className="mt-1 text-xs text-[var(--fg-muted)]">
                  {str(row.detail)}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Risk History</CardTitle>
          </CardHeader>
          <CardContent>
            {historyQ.isLoading ? (
              <p className="text-sm text-[var(--fg-muted)]">Loading history…</p>
            ) : historyPayload.available === false ? (
              <p className="text-sm text-[var(--fg-muted)]">
                Risk history is unavailable right now. No events were invented.
              </p>
            ) : historyItems.length === 0 ? (
              <p className="text-sm text-[var(--fg-muted)]">
                No persisted risk events for this account yet.
              </p>
            ) : (
              <ul className="space-y-2">
                {historyItems.map((item, idx) => (
                  <li
                    key={`${str(item.occurred_at)}-${idx}`}
                    className="rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 text-sm"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium">{str(item.action, "Event")}</span>
                      <span className="text-xs text-[var(--fg-subtle)]">
                        {item.occurred_at
                          ? formatRelativeTime(String(item.occurred_at))
                          : "—"}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-[var(--fg-muted)]">
                      {str(item.message, str(item.outcome, "—"))}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="max-w-xl">
          <CardHeader>
            <CardTitle>Advisory risk check</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-3"
              onSubmit={checkForm.handleSubmit(async (values) => {
                try {
                  const result = await riskApi.check({
                    request_id: `risk_center_${Date.now()}`,
                    symbol: values.symbol,
                    side: values.side,
                    requested_lots: values.volume,
                    entry_price: values.entry_price || undefined,
                    stop_loss_distance: values.stop_distance || undefined,
                    sizing_method: "percentage_risk",
                    risk_per_trade_pct: values.risk_pct || "1",
                    equity: session.equity !== "—" ? session.equity : undefined,
                  });
                  const rec = asRecord(result);
                  setLastRisk(rec);
                  toast.success(`Risk check: ${String(rec.decision ?? "done")}`);
                } catch (e) {
                  toast.error(
                    e instanceof ApiError ? e.message : "Risk check failed",
                  );
                }
              })}
            >
              <div className="space-y-1.5">
                <Label htmlFor="risk-center-symbol">Symbol</Label>
                <Input id="risk-center-symbol" {...checkForm.register("symbol")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="risk-center-side">Side</Label>
                <select
                  id="risk-center-side"
                  className="flex h-10 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-sm"
                  {...checkForm.register("side")}
                >
                  <option value="buy">Buy</option>
                  <option value="sell">Sell</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="risk-center-volume">Volume</Label>
                  <Input id="risk-center-volume" {...checkForm.register("volume")} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="risk-center-risk">Risk %</Label>
                  <Input id="risk-center-risk" {...checkForm.register("risk_pct")} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="risk-center-entry">Entry</Label>
                  <Input
                    id="risk-center-entry"
                    {...checkForm.register("entry_price")}
                    placeholder="optional"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="risk-center-sl">Stop distance</Label>
                  <Input
                    id="risk-center-sl"
                    {...checkForm.register("stop_distance")}
                    placeholder="price units"
                  />
                </div>
              </div>
              <Button type="submit">Run risk check</Button>
            </form>
          </CardContent>
        </Card>

        <RiskRulesPanel risk={lastRisk} />
      </PageMotion>
    </div>
  );
}
