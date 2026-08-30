"use client";

import { memo, useMemo } from "react";
import { CheckCircle2, Circle, ShieldAlert } from "lucide-react";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn } from "@/lib/utils";
import { num } from "@/lib/desk";
import {
  formatRiskRejection,
  parseRiskRules,
} from "@/components/execution/risk-rules-panel";
import { isGoldSymbol } from "@/lib/trading/gold-only";

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
  /**
   * Explicit market session from tick/candle API.
   * null = unknown — do not invent Closed from a missing quote alone.
   */
  marketOpen?: boolean | null;
  /** Catalogue / symbol known independently of live quotes. */
  symbolAvailable?: boolean | null;
};

/** XAUUSD desk spread ceiling (absolute price units). */
export function defaultMaxSpread(): number {
  return 2;
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

/** Live pre-trade gate — compact on Terminal; detailed rules live on Risk Center. */
export const PreTradeChecklist = memo(function PreTradeChecklist({
  inputs,
  className,
  compact = false,
}: {
  inputs: PreTradeInputs;
  className?: string;
  compact?: boolean;
}) {
  const session = useTradingSession();
  const spread =
    Number.isFinite(inputs.bid) &&
    Number.isFinite(inputs.ask) &&
    inputs.bid != null &&
    inputs.ask != null
      ? inputs.ask - inputs.bid
      : NaN;
  const hasQuote = Number.isFinite(spread) && spread > 0;
  const maxSpread = inputs.maxSpread ?? defaultMaxSpread();
  const goldDesk = isGoldSymbol(inputs.symbol);
  // Gold desk ceiling (≤2.00 absolute price) must not be applied to BTC/FX/etc.
  // Non-gold still requires a live quote; Risk/OMS remain authoritative.
  const spreadOk = goldDesk
    ? hasQuote && spread <= maxSpread
    : hasQuote;
  const spreadDetail = !hasQuote
    ? "n/a"
    : goldDesk
      ? `${spread.toFixed(5)} ≤ ${maxSpread}`
      : `${spread.toFixed(5)} · gold desk ≤${maxSpread} N/A · backend Risk validates`;
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

  const marketOpenExplicit = inputs.marketOpen;
  const symbolOk =
    inputs.symbolAvailable != null
      ? inputs.symbolAvailable
      : session.connected && Boolean(inputs.symbol.trim());

  const checks = useMemo(() => {
    const list = [
      {
        ok: session.gatewayOnline === true,
        label: "Gateway Connected",
        detail:
          session.gatewayOnline === true
            ? "Connected"
            : session.gatewayOnline == null
              ? "unknown"
              : session.gatewayLabel || "unavailable",
      },
      {
        ok: session.connected,
        label: "Broker Connected",
        detail: session.connected ? session.server : "offline",
      },
      {
        ok: symbolOk,
        label: "Symbol Available",
        detail: symbolOk ? inputs.symbol || "—" : "unavailable",
      },
      {
        ok: marketOpenExplicit === true || (marketOpenExplicit == null && hasQuote),
        label: "Market Open",
        detail:
          marketOpenExplicit === false
            ? "Market Closed"
            : marketOpenExplicit === true || hasQuote
              ? "Open"
              : "unknown",
      },
      {
        ok: hasQuote,
        label: "Quote",
        detail: hasQuote ? `spread ${spread.toFixed(5)}` : "No Tick",
      },
      {
        ok: spreadOk,
        label: "Spread Acceptable",
        detail: spreadDetail,
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
        ok:
          session.executionEnabled === true ||
          (session.executionEnabled == null &&
            session.connected &&
            marketOpenExplicit !== false &&
            hasQuote),
        label: "Trading Enabled",
        detail:
          session.executionEnabled === false
            ? "execution disabled"
            : marketOpenExplicit === false
              ? "Market Closed"
              : session.executionEnabled === true
                ? "enabled"
                : session.connected && hasQuote
                  ? "session live"
                  : "unknown",
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
    spreadOk,
    spreadDetail,
    goldDesk,
    vol,
    free,
    marginNeeded,
    hasQuote,
    marketOpenExplicit,
    symbolOk,
  ]);

  const blocked = checks.some((c) => !c.ok);
  const failed = checks.filter((c) => !c.ok);
  const visible = compact ? (blocked ? failed : []) : checks;

  return (
    <div className={cn("space-y-2", className)}>
      <div
        className="rounded-md border border-[var(--border)] bg-[var(--surface-2)]/70 px-2.5 py-2"
        aria-live="polite"
      >
        <div className="mb-1.5 flex items-center justify-between gap-2">
          <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Pre-trade
          </p>
          {blocked ? (
            <span className="inline-flex items-center gap-1 text-[10px] text-[var(--danger)]">
              <ShieldAlert className="h-3 w-3" /> Blocked
            </span>
          ) : (
            <span className="text-[10px] text-[var(--success)]">
              Ready · {checks.length} checks
            </span>
          )}
        </div>
        {visible.length > 0 ? (
          <ul className="space-y-1">
            {visible.map((c) => (
              <Row key={c.label} {...c} />
            ))}
          </ul>
        ) : null}
        {blocked ? (
          <p className="mt-1.5 text-[10px] text-[var(--danger)]">
            {inputs.riskDecision === "REJECT" && inputs.riskAssessment
              ? formatRiskRejection(inputs.riskAssessment)
              : failed.map((c) => c.label).join(", ")}
          </p>
        ) : compact ? (
          <p className="text-[10px] text-[var(--fg-subtle)]">
            Detailed rules on{" "}
            <a href="/risk-center" className="text-[var(--accent)] hover:underline">
              Risk Center
            </a>
          </p>
        ) : null}
      </div>
    </div>
  );
});

export function preTradeAllowsExecution(inputs: PreTradeInputs, session: {
  gatewayOnline: boolean | null;
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
  const maxSpread = inputs.maxSpread ?? defaultMaxSpread();
  const goldDesk = isGoldSymbol(inputs.symbol);
  const vol = num(inputs.volume, 0);
  const free = num(session.freeMargin, NaN);
  const marginNeeded = num(inputs.marginRequired, NaN);
  // API/gateway unknown must block new entries (not invent connected).
  if (session.gatewayOnline !== true || !session.connected) return false;
  if (inputs.marketOpen === false) return false;
  if (!inputs.symbol.trim() || vol <= 0) return false;
  if (!Number.isFinite(spread) || spread <= 0) return false;
  // Gold desk absolute ceiling only — never apply XAUUSD ≤2.00 to BTC/FX.
  if (goldDesk && spread > maxSpread) return false;
  if (Number.isFinite(marginNeeded) && Number.isFinite(free) && marginNeeded > free)
    return false;
  if (inputs.validationValid === false) return false;
  if (inputs.riskDecision === "REJECT") return false;
  return true;
}
