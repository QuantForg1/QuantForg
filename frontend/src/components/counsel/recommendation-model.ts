"use client";

import { asList, asRecord, num, str } from "@/lib/desk";

/** Normalized recommendation — every field from API or explicitly empty. */
export type CounselRecommendation = {
  action: string;
  reason: string;
  evidence: string[];
  confidence: number | null;
  impact: string;
  approval: "awaiting" | "approved_advisory" | "held" | "unavailable";
  symbol: string;
  riskLevel: string;
  lotSize: string;
  sl: string;
  tp: string;
  rr: string;
};

export function parseDecisionRecommendation(
  decisionRoot: Record<string, unknown> | null,
  symbolFallback: string,
): CounselRecommendation | null {
  if (!decisionRoot) return null;
  const decision = asRecord(decisionRoot.decision ?? decisionRoot);
  if (!Object.keys(decision).length && !decisionRoot.decision) {
    // empty dashboard
  }
  const stance = str(decision.decision, "WAIT").toUpperCase();
  const explanation = asRecord(decision.explanation);
  const risk = asRecord(decision.risk);
  const analysis = asRecord(decision.analysis);
  const mtf = asRecord(decision.multi_timeframe);

  const evidence: string[] = [];
  const summary = str(explanation.summary);
  if (summary) evidence.push(summary);
  const whyExists = str(explanation.why_it_exists);
  if (whyExists) evidence.push(whyExists);
  const trend = str(analysis.trend ?? analysis.structure);
  if (trend) evidence.push(`Structure · ${trend}`);
  if (mtf.aligned === true) evidence.push("Multi-timeframe aligned");
  if (mtf.aligned === false) evidence.push("Multi-timeframe not aligned");
  for (const w of asList(risk.warnings).map((v) => str(v)).slice(0, 2)) {
    if (w) evidence.push(`Warning · ${w}`);
  }
  for (const r of asList(risk.rejects).map((v) => str(v)).slice(0, 2)) {
    if (r) evidence.push(`Reject · ${r}`);
  }

  const conf = num(decision.confidence_pct);
  const isWait = stance === "WAIT" || !stance;
  const riskAccepted = risk.accepted === true;

  let approval: CounselRecommendation["approval"] = "awaiting";
  if (str(decision.status) === "unavailable" || str(decision.reason).includes("Unable")) {
    approval = "unavailable";
  } else if (isWait || !riskAccepted) {
    approval = "held";
  } else if (stance === "TRADE_IDEA") {
    approval = "approved_advisory";
  }

  return {
    action: isWait ? "WAIT" : stance === "TRADE_IDEA" ? "TRADE_IDEA" : stance,
    reason: str(
      explanation.summary,
      str(decision.reason, isWait ? "Capital preservation — default WAIT" : "—"),
    ),
    evidence,
    confidence: Number.isFinite(conf) ? conf : null,
    impact: buildImpact(decision, risk),
    approval,
    symbol: str(decision.symbol, symbolFallback),
    riskLevel: str(decision.risk_level, "—"),
    lotSize:
      decision.lot_size == null ? "—" : String(decision.lot_size),
    sl:
      decision.recommended_sl == null
        ? "—"
        : String(decision.recommended_sl),
    tp:
      decision.recommended_tp == null
        ? "—"
        : String(decision.recommended_tp),
    rr:
      decision.expected_rr == null ? "—" : String(decision.expected_rr),
  };
}

function buildImpact(
  decision: Record<string, unknown>,
  risk: Record<string, unknown>,
): string {
  const heat = str(asRecord(decision.analysis).portfolio_heat);
  if (heat) return `Portfolio heat · ${heat}`;
  if (risk.accepted === false) return "Risk gate rejected — no book impact advised";
  if (decision.lot_size != null) return `Suggested size ${String(decision.lot_size)} lots (advisory)`;
  return "No quantified impact in payload";
}
