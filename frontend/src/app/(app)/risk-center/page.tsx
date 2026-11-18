"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
import { PersonalRiskProfile } from "@/components/risk/personal-risk-profile";
import {
  aiTradingIntelligenceApi,
  householdPortfolioApi,
  riskApi,
  tradingSessionApi,
} from "@/lib/api/endpoints";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { ApiError } from "@/lib/api/client";
import { useTradingSession } from "@/providers/trading-session-provider";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import { liveTradingLabel } from "@/lib/trading/trader-ux";

const checkSchema = z.object({
  symbol: z.string().min(1),
  side: z.enum(["buy", "sell"]),
  volume: z.string().min(1),
  entry_price: z.string().optional(),
  stop_distance: z.string().optional(),
  risk_pct: z.string().optional(),
});

export default function RiskCenterPage() {
  const session = useTradingSession();
  const [lastRisk, setLastRisk] = useState<Record<string, unknown> | null>(null);
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
  const tradingSessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    staleTime: 10_000,
    refetchInterval: 15_000,
    retry: false,
  });
  const householdRiskQ = useQuery({
    queryKey: ["portfolio-household-risk-center"],
    queryFn: () => householdPortfolioApi.riskCheck({}),
    retry: false,
    staleTime: 15_000,
  });
  const atiRiskQ = useQuery({
    queryKey: ["ati-risk-center-alerts"],
    queryFn: () =>
      aiTradingIntelligenceApi.riskAlerts({
        portfolio: {
          drawdown_pct: String(num(session.profit) < 0 ? Math.abs(num(session.profit)) : 0),
        },
        strategy_health: {},
        execution: {},
      }),
    retry: false,
    staleTime: 20_000,
  });
  const tradingSnap = asRecord(tradingSessionQ.data);
  const householdRisk = asRecord(householdRiskQ.data);
  const ordersMaySubmit =
    tradingSnap.orders_may_submit === true && householdRisk.allowed !== false;
  const riskLocked =
    tradingSnap.risk_locked === true ||
    tradingSnap.daily_loss_exceeded === true ||
    householdRisk.allowed === false ||
    String(tradingSnap.ownership_block_reason || "")
      .toLowerCase()
      .includes("risk");
  const emergencyStop =
    tradingSnap.emergency_stop === true ||
    tradingSnap.kill_switch_armed === true ||
    String(tradingSnap.live_trading_state || "")
      .toUpperCase()
      .includes("KILL");
  const liveAuthorization = liveTradingLabel(tradingSnap);

  const prefs = asRecord(prefsQ.data);
  const effective = asRecord(prefs.effective);
  const protections = asList(prefs.protections).map(asRecord);
  const historyPayload = asRecord(historyQ.data);
  const historyItems = asList(historyPayload.items).map(asRecord);

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
        eyebrow="Risk"
        title="Risk Center"
        description="Your own risk profile drives every trade the robot takes for you. Platform protections and the mandatory stop-loss stay enforced on the server."
        status={<Badge tone="success">Per-user risk profile</Badge>}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/notifications">Notifications</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/ai-robot">Robot desk</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/positions">Positions</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/ai-trading-intelligence">AI Intelligence</Link>
            </Button>
          </div>
        }
      />

      <PageMotion className="space-y-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">AI risk alerts (advisory)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-[12px] text-[var(--fg-muted)]">
            <p>
              Explainable recommendations only — Risk Center prefs and server
              gates remain authoritative. Never auto-mutates kill-switch.
            </p>
            {asList(asRecord(atiRiskQ.data).alerts).length === 0 ? (
              <p>No AI alerts from current session facts.</p>
            ) : (
              <ul className="space-y-1">
                {asList(asRecord(atiRiskQ.data).alerts)
                  .map(asRecord)
                  .map((a) => (
                    <li key={str(a.code)}>
                      [{str(a.severity)}] {str(a.title)} — {str(a.recommended_action)}
                    </li>
                  ))}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card className="border-[color-mix(in_srgb,var(--accent)_28%,var(--border))] bg-[color-mix(in_srgb,var(--accent-soft)_35%,var(--surface))]">
          <CardContent className="grid gap-3 py-4 sm:grid-cols-2">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--accent)]">
                Your preferences
              </p>
              <p className="mt-1 text-sm text-[var(--fg-muted)]">
                Your risk profile below is yours alone. Unchanged settings
                use the platform defaults; the robot applies your values to
                your next trades.
              </p>
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Platform-enforced limits
              </p>
              <p className="mt-1 text-sm text-[var(--fg-muted)]">
                Hard limits, the mandatory stop-loss and global restrictions
                are managed by QuantForg and enforced on the server for every
                order.
              </p>
            </div>
          </CardContent>
        </Card>

        <RiskIntelligencePanel
          equity={session.equity}
          balance={session.balance}
          floatingPnl={floating}
          todayPnl={todayPnl}
          openPositionCount={session.positions.length}
          riskLocked={riskLocked}
          emergencyStop={emergencyStop}
          liveAuthorization={liveAuthorization}
          ordersMaySubmit={ordersMaySubmit}
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

        <PersonalRiskProfile />

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
