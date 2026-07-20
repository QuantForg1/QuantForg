"use client";

import { memo, useMemo } from "react";
import { CheckCircle2, Circle, ShieldAlert } from "lucide-react";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn } from "@/lib/utils";
import { num } from "@/lib/desk";
import {
  formatRiskRejection,
  parseRiskRules,
  RiskRulesPanel,
} from "@/components/execution/risk-rules-panel";

export type PreTradeInputs = {
  symbol: string;
  volume: string;
  bid?: number;
  ask?: number;
  stopLoss?: string;
  takeProfit?: string;
  validationValid?: boolean | null;
  riskDecision?: string | null;
  riskAssessment?: Record<string, unknown> | null;
  marginRequired?: string | null;
  maxSpread?: number;
};

/** Symbol-aware spread ceiling (price units). Gold needs a wider band than FX. */
export function defaultMaxSpread(symbol: string): number {
  const u = symbol.trim().toUpperCase();
  if (u.includes("XAU") || u.includes("GOLD")) return 5;
  if (u.includes("XAG") || u.includes("SILVER")) return 0.5;
  if (u.includes("BTC") || u.includes("ETH")) return 50;
  return 0.05;
}

function Row({ ok, label, detail }: { ok: boolean; label: string; detail: string }) {
  return (
    <li className="flex items-start gap-2 text-[11px]">
      {ok ? (
        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--success)]" />
      ) : (
        <Circle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--fg-subtle)]" />
      )}
      <span>
        <span className={ok ? "text-[var(--fg)]" : "text-[var(--fg-muted)]"}>{label}</span>
        <span className="ml-1 text-[var(--fg-subtle)]">{detail}</span>
      </span>
    </li>
  );
}

/** Live pre-trade gate — every check uses TradingSession + ticket quotes (no mock). */
export const PreTradeChecklist = memo(function PreTradeChecklist({
  inputs,
  className,
}: {
  inputs: PreTradeInputs;
  className?: string;
}) {
  const session = useTradingSession();
  const spread =
    Number.isFinite(inputs.bid) &&
    Number.isFinite(inputs.ask) &&
    inputs.bid != null &&
    inputs.ask != null
      ? inputs.ask - inputs.bid
      : NaN;
  const maxSpread = inputs.maxSpread ?? defaultMaxSpread(inputs.symbol);
  const vol = num(inputs.volume, 0);
  const free = num(session.freeMargin, NaN);
  const marginNeeded = num(inputs.marginRequired, NaN);
  const riskDetail = useMemo(() => {
    if (!inputs.riskDecision) return "pending check";
    if (inputs.riskDecision === "REJECT" && inputs.riskAssessment) {
      const failed = parseRiskRules(inputs.riskAssessment).filter((r) => r.status === "fail");
      if (failed[0]) {
        return `REJECT · ${failed[0].name} ${failed[0].current} > ${failed[0].threshold}`;
      }
      return formatRiskRejection(inputs.riskAssessment);
    }
    return String(inputs.riskDecision);
  }, [inputs.riskDecision, inputs.riskAssessment]);

  const checks = useMemo(() => {
    const list = [
      {
        ok: session.gatewayOnline,
        label: "Gateway Connected",
        detail: session.gatewayLabel,
      },
      {
        ok: session.connected,
        label: "Broker Connected",
        detail: session.connected ? session.server : "offline",
      },
      {
        ok: session.connected && Boolean(inputs.symbol.trim()),
        label: "Symbol Available",
        detail: inputs.symbol || "—",
      },
      {
        ok: Number.isFinite(spread) && spread > 0,
        label: "Market Open / Quote",
        detail: Number.isFinite(spread) ? `spread ${spread.toFixed(5)}` : "no tick",
      },
      {
        ok: Number.isFinite(spread) && spread <= maxSpread,
        label: "Spread Acceptable",
        detail: Number.isFinite(spread)
          ? `${spread.toFixed(5)} ≤ ${maxSpread}`
          : "n/a",
      },
      {
        ok: vol > 0,
        label: "Volume Allowed",
        detail: String(inputs.volume || "—"),
      },
      {
        ok:
          !Number.isFinite(marginNeeded) ||
          !Number.isFinite(free) ||
          marginNeeded <= free,
        label: "Margin Enough",
        detail:
          Number.isFinite(marginNeeded) && Number.isFinite(free)
            ? `need ${marginNeeded} / free ${free}`
            : session.freeMargin,
      },
      {
        ok: inputs.riskDecision == null || inputs.riskDecision !== "REJECT",
        label: "Risk Allowed",
        detail: riskDetail,
      },
      {
        ok: inputs.validationValid !== false,
        label: "Order Valid",
        detail:
          inputs.validationValid === true
            ? "validated"
            : inputs.validationValid === false
              ? "failed"
              : "awaiting",
      },
      {
        ok: !inputs.stopLoss || num(inputs.stopLoss, NaN) > 0,
        label: "SL Valid",
        detail: inputs.stopLoss || "optional",
      },
      {
        ok: !inputs.takeProfit || num(inputs.takeProfit, NaN) > 0,
        label: "TP Valid",
        detail: inputs.takeProfit || "optional",
      },
      {
        ok: session.connected,
        label: "Trading Enabled",
        detail: session.connected ? "session live" : "blocked",
      },
    ];
    return list;
  }, [
    session,
    inputs.symbol,
    inputs.volume,
    inputs.stopLoss,
    inputs.takeProfit,
    inputs.validationValid,
    inputs.riskDecision,
    riskDetail,
    spread,
    maxSpread,
    vol,
    free,
    marginNeeded,
  ]);

  const blocked = checks.some((c) => !c.ok);
  const failed = checks.filter((c) => !c.ok).map((c) => c.label);

  return (
    <div className={cn("space-y-2", className)}>
      <div
        className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/70 px-3 py-2.5"
        aria-live="polite"
      >
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Pre-trade checklist
          </p>
          {blocked ? (
            <span className="inline-flex items-center gap-1 text-[10px] text-[var(--danger)]">
              <ShieldAlert className="h-3 w-3" /> Blocked
            </span>
          ) : (
            <span className="text-[10px] text-[var(--success)]">Ready</span>
          )}
        </div>
        <ul className="space-y-1.5">{checks.map((c) => <Row key={c.label} {...c} />)}</ul>
        {blocked ? (
          <p className="mt-2 text-[10px] text-[var(--danger)]">
            Execution blocked:{" "}
            {inputs.riskDecision === "REJECT" && inputs.riskAssessment
              ? formatRiskRejection(inputs.riskAssessment)
              : failed.join(", ")}
            .
          </p>
        ) : null}
      </div>
      <RiskRulesPanel risk={inputs.riskAssessment ?? null} />
    </div>
  );
});

export function preTradeAllowsExecution(inputs: PreTradeInputs, session: {
  gatewayOnline: boolean;
  connected: boolean;
  freeMargin: string;
}): boolean {
  const spread =
    Number.isFinite(inputs.bid) &&
    Number.isFinite(inputs.ask) &&
    inputs.bid != null &&
    inputs.ask != null
      ? inputs.ask - inputs.bid
      : NaN;
  const maxSpread = inputs.maxSpread ?? defaultMaxSpread(inputs.symbol);
  const vol = num(inputs.volume, 0);
  const free = num(session.freeMargin, NaN);
  const marginNeeded = num(inputs.marginRequired, NaN);
  if (!session.gatewayOnline || !session.connected) return false;
  if (!inputs.symbol.trim() || vol <= 0) return false;
  if (!Number.isFinite(spread) || spread <= 0 || spread > maxSpread) return false;
  if (Number.isFinite(marginNeeded) && Number.isFinite(free) && marginNeeded > free)
    return false;
  if (inputs.validationValid === false) return false;
  if (inputs.riskDecision === "REJECT") return false;
  return true;
}
