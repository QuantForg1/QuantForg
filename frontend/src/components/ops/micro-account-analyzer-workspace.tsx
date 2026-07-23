"use client";

import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { microAccountAnalyzerApi } from "@/lib/api/endpoints";
import { asList, asRecord, bool, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const BALANCES = ["50", "100", "250", "500"] as const;
const RISK_LADDER = ["0.25", "0.50", "0.75", "1.00", "1.50", "2.00"] as const;

export function MicroAccountAnalyzerWorkspace() {
  const [balance, setBalance] = useState<string>("50");
  const [riskPct, setRiskPct] = useState<string>("2.00");
  const [atrOverride, setAtrOverride] = useState<string>("");
  const [report, setReport] = useState<Record<string, unknown> | null>(null);

  const analyzeM = useMutation({
    mutationFn: () =>
      microAccountAnalyzerApi.analyze({
        balance,
        risk_pct: riskPct,
        atr: atrOverride.trim() ? atrOverride.trim() : null,
        use_live_broker: true,
        use_live_atr: !atrOverride.trim(),
      }),
    onSuccess: (data) => setReport(asRecord(data)),
  });

  useEffect(() => {
    analyzeM.mutate();
    // Initial load only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (analyzeM.isPending && !report) return <DeskSkeleton rows={8} />;
  if (analyzeM.isError && !report) {
    return (
      <DeskError
        message={
          analyzeM.error instanceof Error
            ? analyzeM.error.message
            : "Micro Account Analyzer unavailable"
        }
        onRetry={() => analyzeM.mutate()}
      />
    );
  }

  const root = report ?? {};
  const specs = asRecord(root.broker_specs);
  const profiles = asRecord(root.profiles);
  const institutional = asRecord(profiles.INSTITUTIONAL);
  const micro = asRecord(profiles.MICRO_ACCOUNT_MODE);
  const eligible = bool(root.eligible);
  const flow = asList(root.flow).map(asRecord);
  const minSafe = asList(root.min_safe_balances_by_risk).map(asRecord);
  const matrix = asList(root.supported_balance_matrix).map(asRecord);
  const fiftyClear = str(root.fifty_dollar_clear_statement, "");
  const microCompatible = bool(specs.micro_account_compatible);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">MICRO ACCOUNT MODE</Badge>
        <Badge tone="success">INSTITUTIONAL FROZEN</Badge>
        {microCompatible ? (
          <Badge tone="success">Micro account compatible</Badge>
        ) : (
          <Badge tone="warning">Standard min lot</Badge>
        )}
        <Button
          size="sm"
          variant="secondary"
          disabled={analyzeM.isPending}
          onClick={() => analyzeM.mutate()}
        >
          {analyzeM.isPending ? "Analyzing…" : "Re-analyze"}
        </Button>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <OpsPanel title="Trading profiles">
          <div className="grid gap-3 sm:grid-cols-2">
            <MetricCard
              label="INSTITUTIONAL"
              value={`Q${str(institutional.quality, "80")} / C${str(institutional.confluence, "80")} · ${str(institutional.risk_pct, "1.0")}%`}
              tone="ok"
            />
            <MetricCard
              label="MICRO ACCOUNT"
              value={`Targets $50–$500 · hard max ${str(micro.hard_max_risk_pct, "5.0")}%`}
            />
          </div>
          <p className="mt-2 text-[12px] text-[var(--fg-muted)]">
            Institutional Mode is frozen. This analyzer never weakens Q/C/1% risk,
            Strategy, OMS, Safety, or institutional sizing policy.
          </p>
        </OpsPanel>

        <OpsPanel title="Controls">
          <div className="space-y-3">
            <div>
              <p className="mb-1.5 text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Balance
              </p>
              <div className="flex flex-wrap gap-1.5">
                {BALANCES.map((b) => (
                  <Button
                    key={b}
                    size="sm"
                    variant={balance === b ? "default" : "outline"}
                    onClick={() => setBalance(b)}
                  >
                    ${b}
                  </Button>
                ))}
              </div>
            </div>
            <div>
              <p className="mb-1.5 text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Risk %
              </p>
              <div className="flex flex-wrap gap-1.5">
                {RISK_LADDER.map((r) => (
                  <Button
                    key={r}
                    size="sm"
                    variant={riskPct === r ? "default" : "outline"}
                    onClick={() => setRiskPct(r)}
                  >
                    {r}%
                  </Button>
                ))}
              </div>
            </div>
            <div>
              <label
                className="mb-1.5 block text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]"
                htmlFor="micro-atr"
              >
                ATR override (optional)
              </label>
              <input
                id="micro-atr"
                className="w-full border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 font-mono text-[13px] text-[var(--fg)] tabular-nums outline-none focus:border-[var(--fg-muted)]"
                placeholder="Live M15 ATR when empty"
                value={atrOverride}
                onChange={(e) => setAtrOverride(e.target.value)}
              />
            </div>
          </div>
        </OpsPanel>
      </div>

      <OpsPanel title="Analysis flow">
        <ol className="space-y-2">
          {flow.map((step, i) => (
            <li
              key={`${str(step.step)}-${i}`}
              className="grid grid-cols-[140px_1fr] gap-3 border-b border-[var(--border)] pb-2 last:border-0"
            >
              <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                {str(step.step)}
              </span>
              <span
                className={cn(
                  "font-mono text-[13px] tabular-nums text-[var(--fg)]",
                  str(step.step) === "Eligible" &&
                    (eligible ? "text-[var(--success)]" : "text-[var(--danger)]"),
                )}
              >
                {str(step.value)}
              </span>
            </li>
          ))}
        </ol>
      </OpsPanel>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Eligible"
          value={eligible ? "YES" : "NO"}
          tone={eligible ? "ok" : "bad"}
        />
        <MetricCard
          label="Calculated lots"
          value={str(root.calculated_lots, "0")}
        />
        <MetricCard
          label="Max loss"
          value={`$${str(root.maximum_loss, "—")}`}
        />
        <MetricCard
          label="Recommended risk %"
          value={str(root.recommended_risk_pct, "—")}
        />
      </div>

      <OpsPanel title="Broker specs">
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <MetricCard label="Min lot" value={str(specs.volume_min, "—")} />
          <MetricCard label="Lot step" value={str(specs.volume_step, "—")} />
          <MetricCard label="Contract" value={str(specs.contract_size, "—")} />
          <MetricCard label="Tick size" value={str(specs.tick_size, "—")} />
          <MetricCard label="Tick value" value={str(specs.tick_value, "—")} />
          <MetricCard label="Source" value={str(specs.source, "—")} />
        </div>
        <p className="mt-2 text-[12px] text-[var(--fg-muted)]">
          {microCompatible
            ? "Micro account compatible — broker supports ≤0.001 lots. Current broker settings are not changed."
            : "Broker minimum is fixed for this account. We do not override min lot or force 0.01 fills."}
        </p>
      </OpsPanel>

      {fiftyClear ? (
        <OpsPanel title="$50 XAUUSD clear finding">
          <p className="text-[13px] leading-relaxed text-[var(--danger)]">
            {fiftyClear}
          </p>
        </OpsPanel>
      ) : null}

      <OpsPanel title="Minimum safe balance for this broker">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                <th className="py-2 pr-3 font-medium">Risk %</th>
                <th className="py-2 pr-3 font-medium">Min safe balance</th>
                <th className="py-2 font-medium">$ risk @ min lot</th>
              </tr>
            </thead>
            <tbody>
              {minSafe.map((row) => (
                <tr
                  key={str(row.risk_pct)}
                  className="border-b border-[var(--border)]/60"
                >
                  <td className="py-2 pr-3 font-mono text-[13px] tabular-nums">
                    {str(row.risk_pct)}%
                  </td>
                  <td className="py-2 pr-3 font-mono text-[13px] tabular-nums">
                    ${str(row.min_safe_balance)}
                  </td>
                  <td className="py-2 font-mono text-[13px] tabular-nums">
                    ${str(row.dollar_risk_at_min_lot)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </OpsPanel>

      <OpsPanel title="Supported balances">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                <th className="py-2 pr-3 font-medium">Balance</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Lots</th>
                <th className="py-2 pr-3 font-medium">Max loss</th>
                <th className="py-2 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              {matrix.map((row) => {
                const ok = bool(row.eligible);
                return (
                  <tr
                    key={str(row.balance)}
                    className="border-b border-[var(--border)]/60 align-top"
                  >
                    <td className="py-2 pr-3 font-mono text-[13px] tabular-nums">
                      ${str(row.balance)}
                    </td>
                    <td
                      className={cn(
                        "py-2 pr-3 text-[12px] font-semibold",
                        ok ? "text-[var(--success)]" : "text-[var(--danger)]",
                      )}
                    >
                      {str(row.status)}
                    </td>
                    <td className="py-2 pr-3 font-mono text-[13px] tabular-nums">
                      {str(row.calculated_lots)}
                    </td>
                    <td className="py-2 pr-3 font-mono text-[13px] tabular-nums">
                      ${str(row.max_loss)}
                    </td>
                    <td className="py-2 text-[12px] text-[var(--fg-muted)]">
                      {str(row.reason)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </OpsPanel>
    </div>
  );
}
