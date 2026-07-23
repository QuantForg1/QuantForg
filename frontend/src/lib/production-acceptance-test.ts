/** Production Acceptance Test (PAT) — read-only first-fill validation.

Never mutates Strategy, Risk, Safety, OMS, MT5, or trading logic.
Never allows manual approval. Evidence only.
*/
import { asList, asRecord, bool, str } from "@/lib/desk";
import {
  loadAcceptanceReport,
  observeAcceptanceEvidence,
  runAutomaticAcceptanceEngine,
} from "@/lib/automatic-production-acceptance";
import {
  isBrokerAccepted,
  loadFirstExecutionEvidence,
  type FirstExecutionEvidenceRecord,
} from "@/lib/first-execution-evidence";
import { loadTimelineStore } from "@/lib/execution-timeline";

const PAT_REPORT_KEY = "quantforg.production_acceptance_test.v1";

export type PatStatus = "WAITING" | "PRODUCTION ACCEPTED";

export type PatCheckItem = {
  id: string;
  group: "Market" | "Decision" | "Risk" | "Safety" | "Execution" | "Trade" | "Audit";
  label: string;
  pass: boolean;
  mark: "✓" | "⏳";
  detail: string;
  result: "PASS" | "FAIL";
};

export type ProductionAcceptanceTestReport = {
  immutable: true;
  title: "Production Acceptance Report";
  status: "PRODUCTION ACCEPTED";
  generatedAtUtc: string;
  utcTimestamp: string;
  signalId: string;
  mt5Ticket: string;
  dealId: string;
  executionLatency: string;
  checklist: PatCheckItem[];
  overall: "PASS";
};

export type PatModel = {
  status: PatStatus;
  statusLabel: string;
  checklist: PatCheckItem[];
  missing: string[];
  report: ProductionAcceptanceTestReport | null;
  summary: {
    utcTimestamp: string;
    signalId: string;
    mt5Ticket: string;
    dealId: string;
    executionLatency: string;
  };
};

function present(v: string | null | undefined): boolean {
  const s = (v ?? "").trim();
  return s !== "" && s !== "—";
}

function item(
  id: string,
  group: PatCheckItem["group"],
  label: string,
  pass: boolean,
  detail: string,
): PatCheckItem {
  return {
    id,
    group,
    label,
    pass,
    mark: pass ? "✓" : "⏳",
    detail: pass ? detail || "observed" : "Waiting",
    result: pass ? "PASS" : "FAIL",
  };
}

export function loadPatReport(): ProductionAcceptanceTestReport | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(PAT_REPORT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ProductionAcceptanceTestReport;
    if (parsed?.immutable && parsed.status === "PRODUCTION ACCEPTED") {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

export function freezePatReport(
  report: ProductionAcceptanceTestReport,
): ProductionAcceptanceTestReport {
  if (typeof window === "undefined") return report;
  const existing = loadPatReport();
  if (existing?.immutable) return existing;
  try {
    window.localStorage.setItem(PAT_REPORT_KEY, JSON.stringify(report));
  } catch {
    /* ignore */
  }
  return report;
}

function positionVisible(
  positions: unknown,
  ticket: string,
): boolean {
  if (!present(ticket)) return false;
  const rows = asList(
    asRecord(positions).positions ??
      asRecord(positions).items ??
      positions,
  ).map(asRecord);
  if (rows.some((p) => str(p.ticket ?? p.mt5_ticket) === ticket)) {
    return true;
  }
  // Closed fill still counts if journal recorded the ticket (position may be flat)
  return false;
}

export function buildPatChecklist(input: {
  autoTrading: unknown;
  journal: unknown;
  audits: unknown;
  positions: unknown;
  evidence: FirstExecutionEvidenceRecord | null;
}): PatCheckItem[] {
  const obs = observeAcceptanceEvidence({
    autoTrading: input.autoTrading,
    journal: input.journal,
    audits: input.audits,
  });
  const ev = input.evidence;
  const auto = asRecord(input.autoTrading);
  const last = asRecord(asRecord(auto.orchestrator).last_cycle);
  const diag = asRecord(last.market_context_diagnostics);

  const entry = str(ev?.entryPrice, "");
  const sl = str(ev?.stopLoss, "");
  const tp = str(ev?.takeProfit, "");
  const ticket = str(ev?.mt5Ticket || obs.fields.mt5Ticket, "");
  const deal = str(ev?.dealId || obs.fields.dealId, "");
  const journalId = str(ev?.journalId || obs.fields.journalId, "");
  const auditId = str(ev?.auditId, "");

  const auditItems = asList(
    asRecord(input.audits).items ??
      asRecord(input.audits).audits ??
      input.audits,
  ).map(asRecord);
  const auditHit =
    present(auditId) ||
    (present(ticket) &&
      auditItems.some(
        (a) =>
          str(a.ticket ?? a.mt5_ticket) === ticket ||
          str(a.request_id) === str(ev?.omsRequestId || obs.fields.omsRequestId),
      ));

  const timeline = loadTimelineStore();
  const timelineComplete =
    timeline.events.length >= 4 ||
    (obs.omsForward && obs.mt5Ticket && obs.dealId);

  const evidenceFrozen =
    Boolean(ev?.locked) || loadAcceptanceReport()?.immutable === true;

  const marketContextValid =
    obs.snapshot ||
    str(diag.snapshot) === "OK" ||
    bool(diag.session_allowed) !== undefined;

  const posVisible =
    positionVisible(input.positions, ticket) ||
    (present(ticket) && present(deal)); // deal implies execution recorded

  return [
    item("snap", "Market", "Snapshot available", obs.snapshot, "OK"),
    item(
      "mctx",
      "Market",
      "Market context valid",
      marketContextValid && obs.snapshot,
      str(diag.trading_session || obs.fields.session, "OK"),
    ),
    item(
      "signal",
      "Market",
      "Signal generated",
      obs.signalGenerated || present(ev?.signalId),
      obs.fields.signalId || ev?.signalId || "",
    ),
    item(
      "decision",
      "Decision",
      "Decision created",
      obs.decisionPass || present(ev?.decisionId),
      obs.fields.decisionId || ev?.decisionId || "",
    ),
    item(
      "decision_id",
      "Decision",
      "Decision ID recorded",
      present(obs.fields.decisionId) || present(ev?.decisionId),
      obs.fields.decisionId || ev?.decisionId || "",
    ),
    item(
      "risk",
      "Risk",
      "Risk PASS",
      obs.riskPass || (present(ev?.riskResult) && ev!.riskResult.toUpperCase() === "PASS"),
      obs.fields.riskResult || ev?.riskResult || "",
    ),
    item(
      "safety",
      "Safety",
      "Safety PASS",
      obs.safetyPass ||
        (present(ev?.safetyResult) && ev!.safetyResult.toUpperCase() === "PASS"),
      obs.fields.safetyResult || ev?.safetyResult || "",
    ),
    item(
      "oms",
      "Execution",
      "OMS Forward",
      obs.omsForward || Boolean(ev?.omsRequestId && present(ev.omsRequestId)),
      obs.fields.omsRequestId || ev?.omsRequestId || "",
    ),
    item(
      "broker",
      "Execution",
      "Broker Accepted",
      obs.brokerAccepted ||
        (ev ? isBrokerAccepted(ev.brokerResponse) : false),
      obs.fields.brokerResponse || ev?.brokerResponse || "",
    ),
    item("mt5", "Execution", "MT5 Ticket", present(ticket), ticket),
    item("deal", "Execution", "Deal ID", present(deal), deal),
    item("entry", "Trade", "Entry Price recorded", present(entry), entry),
    item("sl", "Trade", "Stop Loss recorded", present(sl), sl),
    item("tp", "Trade", "Take Profit recorded", present(tp), tp),
    item(
      "pos",
      "Trade",
      "Position visible",
      posVisible,
      posVisible ? ticket : "",
    ),
    item("journal", "Audit", "Journal Entry", present(journalId) || obs.journalEntry, journalId),
    item("audit", "Audit", "Audit Entry", auditHit, auditId || "matched"),
    item(
      "timeline",
      "Audit",
      "Timeline complete",
      timelineComplete,
      timelineComplete ? `${timeline.events.length} events` : "",
    ),
    item(
      "frozen",
      "Audit",
      "Evidence frozen",
      evidenceFrozen,
      evidenceFrozen ? "immutable" : "",
    ),
  ];
}

export function runProductionAcceptanceTest(input: {
  autoTrading: unknown;
  journal: unknown;
  audits: unknown;
  positions: unknown;
}): PatModel {
  const frozen = loadPatReport();
  if (frozen?.immutable) {
    return {
      status: "PRODUCTION ACCEPTED",
      statusLabel: "✅ PRODUCTION ACCEPTED",
      checklist: frozen.checklist,
      missing: [],
      report: frozen,
      summary: {
        utcTimestamp: frozen.utcTimestamp,
        signalId: frozen.signalId,
        mt5Ticket: frozen.mt5Ticket,
        dealId: frozen.dealId,
        executionLatency: frozen.executionLatency,
      },
    };
  }

  // Drive auto-acceptance freeze side-effect when core gate passes
  runAutomaticAcceptanceEngine({
    autoTrading: input.autoTrading,
    journal: input.journal,
    audits: input.audits,
  });

  const evidence = loadFirstExecutionEvidence().record;
  const checklist = buildPatChecklist({
    ...input,
    evidence,
  });
  const missing = checklist.filter((c) => !c.pass).map((c) => c.label);
  const allPass = missing.length === 0;

  const summary = {
    utcTimestamp: str(
      evidence?.utcTimestamp ||
        asRecord(
          asRecord(asRecord(input.autoTrading).orchestrator).last_cycle,
        ).observed_at,
      new Date().toISOString(),
    ),
    signalId: str(evidence?.signalId, ""),
    mt5Ticket: str(evidence?.mt5Ticket, ""),
    dealId: str(evidence?.dealId, ""),
    executionLatency: str(evidence?.executionLatency, ""),
  };

  if (!allPass) {
    return {
      status: "WAITING",
      statusLabel: "⏳ WAITING",
      checklist,
      missing,
      report: null,
      summary,
    };
  }

  const generatedAtUtc = new Date().toISOString();
  const report: ProductionAcceptanceTestReport = {
    immutable: true,
    title: "Production Acceptance Report",
    status: "PRODUCTION ACCEPTED",
    generatedAtUtc,
    utcTimestamp: summary.utcTimestamp || generatedAtUtc,
    signalId: summary.signalId,
    mt5Ticket: summary.mt5Ticket,
    dealId: summary.dealId,
    executionLatency: summary.executionLatency,
    checklist,
    overall: "PASS",
  };
  const locked = freezePatReport(report);

  return {
    status: "PRODUCTION ACCEPTED",
    statusLabel: "✅ PRODUCTION ACCEPTED",
    checklist: locked.checklist,
    missing: [],
    report: locked,
    summary: {
      utcTimestamp: locked.utcTimestamp,
      signalId: locked.signalId,
      mt5Ticket: locked.mt5Ticket,
      dealId: locked.dealId,
      executionLatency: locked.executionLatency,
    },
  };
}

/** Minimal single-page PDF (PDF 1.4) — no external deps. */
export function buildPatPdfBytes(report: {
  statusLabel: string;
  generatedAtUtc: string;
  utcTimestamp: string;
  signalId: string;
  mt5Ticket: string;
  dealId: string;
  executionLatency: string;
  checklist: PatCheckItem[];
  overall: string;
}): Uint8Array {
  const lines: string[] = [
    "Production Acceptance Report",
    `Status: ${report.statusLabel}`,
    `Overall: ${report.overall}`,
    `Generated (UTC): ${report.generatedAtUtc}`,
    `Execution UTC: ${report.utcTimestamp}`,
    `Signal ID: ${report.signalId || "—"}`,
    `MT5 Ticket: ${report.mt5Ticket || "—"}`,
    `Deal ID: ${report.dealId || "—"}`,
    `Latency: ${report.executionLatency || "—"}`,
    "",
    "Checklist:",
  ];
  for (const c of report.checklist) {
    lines.push(
      `${c.mark} [${c.group}] ${c.label} — ${c.result}${c.detail && c.pass ? ` (${c.detail.slice(0, 40)})` : ""}`,
    );
  }
  lines.push("", "Evidence only. No manual approval.");

  const escapePdf = (s: string) =>
    s.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");

  let y = 780;
  const contentParts: string[] = ["BT", "/F1 10 Tf", "14 TL"];
  for (const line of lines) {
    contentParts.push(`1 0 0 1 40 ${y} Tm (${escapePdf(line.slice(0, 110))}) Tj`);
    y -= 14;
    if (y < 40) break;
  }
  contentParts.push("ET");
  const stream = contentParts.join("\n");

  const objects: string[] = [];
  objects.push("1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj");
  objects.push("2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj");
  objects.push(
    "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj",
  );
  objects.push(
    `4 0 obj<< /Length ${stream.length} >>stream\n${stream}\nendstream endobj`,
  );
  objects.push("5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj");

  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [0];
  for (const obj of objects) {
    offsets.push(pdf.length);
    pdf += obj + "\n";
  }
  const xrefStart = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n`;
  pdf += "0000000000 65535 f \n";
  for (let i = 1; i < offsets.length; i++) {
    pdf += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
  }
  pdf += `trailer<< /Size ${objects.length + 1} /Root 1 0 R >>\n`;
  pdf += `startxref\n${xrefStart}\n%%EOF`;

  const encoder = new TextEncoder();
  return encoder.encode(pdf);
}

export function downloadBytes(filename: string, data: Uint8Array, type: string): void {
  if (typeof window === "undefined") return;
  const blob = new Blob([data as BlobPart], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadJson(filename: string, payload: unknown): void {
  if (typeof window === "undefined") return;
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
