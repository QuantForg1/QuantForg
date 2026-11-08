"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  buildStrategyRules,
  extractBacktestPerformance,
} from "@/components/strategies/strategy-utils";
import { asRecord, str } from "@/lib/desk";

function numish(v: unknown) {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
}

type StrategySidePanelsProps = {
  strategyKey: string;
  category: string;
  description: string;
  symbol: string;
  timeframe: string;
  maxTrades: string;
  dailyLoss: string;
  maxExposure: string;
  onSymbol: (v: string) => void;
  onTimeframe: (v: string) => void;
  onMaxTrades: (v: string) => void;
  onDailyLoss: (v: string) => void;
  lastResult: Record<string, unknown> | null;
  portfolioData: unknown;
};

export function StrategySidePanels({
  strategyKey,
  category,
  description,
  symbol,
  timeframe,
  maxTrades,
  dailyLoss,
  maxExposure,
  onSymbol,
  onTimeframe,
  onMaxTrades,
  onDailyLoss,
  lastResult,
  portfolioData,
}: StrategySidePanelsProps) {
  const signalBlock = lastResult ? asRecord(lastResult.signal) : null;
  const backtestFields = extractBacktestPerformance(lastResult, portfolioData);
  const rules = buildStrategyRules(
    description,
    symbol,
    timeframe,
    maxTrades,
    dailyLoss,
    maxExposure,
  );

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Strategy Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex justify-between gap-3">
            <span className="text-[var(--fg-muted)]">Type</span>
            <span className="font-medium">{category || strategyKey}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-[var(--fg-muted)]">Market</span>
            <span className="font-medium">{symbol}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-[var(--fg-muted)]">Timeframe</span>
            <span className="font-medium">{timeframe}</span>
          </div>
          <p className="text-xs leading-relaxed text-[var(--fg-muted)]">
            {description || "Strategy stays advisory until risk and OMS gates pass."}
          </p>
          <div className="grid gap-2 border-t border-[var(--border)] pt-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Symbol</Label>
              <Input value={symbol} onChange={(e) => onSymbol(e.target.value.toUpperCase())} />
            </div>
            <div className="space-y-1.5">
              <Label>Timeframe</Label>
              <Input value={timeframe} onChange={(e) => onTimeframe(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Max trades</Label>
              <Input value={maxTrades} onChange={(e) => onMaxTrades(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Daily loss %</Label>
              <Input value={dailyLoss} onChange={(e) => onDailyLoss(e.target.value)} />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Performance (Backtest)</CardTitle>
          <p className="text-xs text-[var(--fg-muted)]">
            Reported metrics only — use Research backtests for full history.
          </p>
        </CardHeader>
        <CardContent>
          {signalBlock ? (
            <dl className="mb-4 grid grid-cols-2 gap-3 border-b border-[var(--border)] pb-4 text-sm">
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                  Last action
                </dt>
                <dd className="mt-1 font-semibold">{str(signalBlock.action)}</dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                  Confidence
                </dt>
                <dd className="mt-1 font-semibold tabular">
                  {(numish(signalBlock.confidence) * 100).toFixed(0)}%
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                  Risk gate
                </dt>
                <dd className="mt-1 text-[var(--fg-muted)]">
                  {lastResult?.risk
                    ? asRecord(lastResult.risk).allowed
                      ? "Allowed"
                      : "Blocked"
                    : "—"}
                </dd>
              </div>
            </dl>
          ) : null}

          {backtestFields.length > 0 ? (
            <dl className="grid grid-cols-2 gap-3 text-sm">
              {backtestFields.map((f) => (
                <div key={f.label}>
                  <dt className="text-[11px] uppercase tracking-wide text-[var(--fg-subtle)]">
                    {f.label}
                  </dt>
                  <dd className="mt-1 font-semibold tabular">{f.value}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-sm text-[var(--fg-muted)]">
              Unavailable — no backtest metrics in the latest evaluate or portfolio
              snapshot.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Strategy Rules</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-2 text-sm">
            {rules.map((rule, i) => (
              <li key={`${i}-${rule.slice(0, 24)}`} className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--success)]" />
                <span>
                  <span className="text-[var(--fg-subtle)]">{i + 1}. </span>
                  {rule}
                </span>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
