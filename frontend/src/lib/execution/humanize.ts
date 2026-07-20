/** Human-readable MT5 / pipeline rejection messages — never show bare "Order validation failed". */

const RETCODE_HINTS: Record<number, string> = {
  10004: "Requote — price moved. Retry the order.",
  10006: "Broker rejected the request.",
  10014: "Lot size must match broker volume_step increments.",
  10015: "Invalid price for this order type.",
  10016: "Stop loss / take profit violate broker stop level.",
  10017: "Trading is disabled for this symbol or account.",
  10018: "Market is closed.",
  10019: "Insufficient free margin.",
  10021: "No quotes — market may be closed.",
  10027: "AutoTrading is disabled in MetaTrader 5.",
  10030: "Unsupported filling mode.",
  10031: "No connection to the trade server.",
  90001: "Live execution is disabled (EXECUTION_ENABLED=false).",
};

const PHRASE_HINTS: Array<[RegExp, string]> = [
  [/insufficient free margin|not enough money|no money/i, "Insufficient free margin."],
  [/market (is )?closed/i, "Market is closed."],
  [/volume must align|volume_step|lot size must be/i, "Lot size must be broker volume_step increments."],
  [/unsupported filling|filling mode/i, "Unsupported filling mode."],
  [/autotrading/i, "AutoTrading is disabled in MetaTrader 5."],
  [/invalid stops|stop loss too close|take profit too close/i, "Stop loss / take profit violate broker distance rules."],
];

export function humanExecutionError(
  input: {
    title?: string;
    messages?: unknown;
    message?: unknown;
    retcode?: unknown;
    comment?: unknown;
    rejection_reasons?: unknown;
  },
  fallback = "Order rejected",
): { title: string; description?: string } {
  const msgs = Array.isArray(input.messages)
    ? input.messages.map(String).filter(Boolean)
    : [];
  const reasons = Array.isArray(input.rejection_reasons)
    ? input.rejection_reasons.map(String).filter(Boolean)
    : [];
  const comment = String(input.comment ?? "").trim();
  const message = String(input.message ?? "").trim();
  const retcode = Number(input.retcode);
  const primary =
    msgs[0] ||
    reasons[0] ||
    comment ||
    message ||
    (Number.isFinite(retcode) ? RETCODE_HINTS[retcode] : "") ||
    fallback;

  let title = primary;
  for (const [re, hint] of PHRASE_HINTS) {
    if (re.test(primary)) {
      title = hint;
      break;
    }
  }
  if (Number.isFinite(retcode) && RETCODE_HINTS[retcode] && !msgs.length && !comment) {
    title = RETCODE_HINTS[retcode];
  }

  // Never use the generic toast title as the only signal
  if (/^order validation failed$/i.test(title)) {
    title = msgs[0] || reasons[0] || RETCODE_HINTS[retcode] || "Order did not pass validation.";
  }

  const detailParts = [
    ...msgs.slice(1, 3),
    ...reasons.slice(0, 2),
    Number.isFinite(retcode) && retcode > 0 ? `Retcode ${retcode}` : "",
    comment && comment !== title ? comment : "",
  ].filter(Boolean);

  const unique = [...new Set(detailParts)].filter((p) => p !== title);
  return {
    title,
    description: unique.length ? unique.join(" · ") : undefined,
  };
}

export type ExecutionDiagnosticRow = {
  request_id: string;
  timestamp: string;
  symbol: string;
  side: string;
  action: string;
  outcome: string;
  latency_ms: number | null;
  retcode: number | null;
  comment: string;
  ticket: number | null;
  deal: number | null;
  validation: StageView;
  risk: StageView;
  gateway: StageView;
  order_check: StageView;
  order_send: StageView;
  request_payload: Record<string, unknown> | null;
  response_payload: Record<string, unknown> | null;
};

type StageView = {
  status: string;
  reason: string;
  latency_ms?: number;
  meta?: Record<string, unknown>;
};

function stageOf(
  stages: Array<Record<string, unknown>>,
  names: string[],
): StageView {
  const normalized = names.map((n) => n.toLowerCase().replace(/[\s_]+/g, " "));
  const hit = stages.find((s) => {
    const key = String(s.stage || "")
      .toLowerCase()
      .replace(/[\s_]+/g, " ");
    return normalized.some((n) => key === n || key.includes(n));
  });
  if (!hit) return { status: "—", reason: "—" };
  return {
    status: String(hit.status || "—"),
    reason: String(hit.reason || "—"),
    latency_ms: typeof hit.latency_ms === "number" ? hit.latency_ms : undefined,
    meta: (hit.meta as Record<string, unknown>) || undefined,
  };
}

export function journalToDiagnostics(
  items: Array<Record<string, unknown>>,
): ExecutionDiagnosticRow[] {
  return items.map((row) => {
    const stages = Array.isArray(row.stages)
      ? (row.stages as Array<Record<string, unknown>>)
      : [];
    const meta = (row.meta as Record<string, unknown>) || {};
    const broker = stageOf(stages, [
      "broker submission",
      "broker acceptance",
      "broker fill",
    ]);
    const validation = stageOf(stages, ["validation"]);
    const risk = stageOf(stages, ["risk check", "execution check"]);
    const retcode =
      typeof meta.retcode === "number"
        ? meta.retcode
        : typeof broker.meta?.retcode === "number"
          ? (broker.meta.retcode as number)
          : null;
    return {
      request_id: String(row.request_id || ""),
      timestamp: String(row.timestamp || ""),
      symbol: String(row.symbol || ""),
      side: String(row.side || ""),
      action: String(row.action || "submit"),
      outcome: String(row.execution_result || ""),
      latency_ms: typeof row.latency_ms === "number" ? row.latency_ms : null,
      retcode,
      comment: String(row.reason || broker.reason || ""),
      ticket: typeof row.ticket === "number" ? row.ticket : null,
      deal: typeof meta.deal_ticket === "number" ? (meta.deal_ticket as number) : null,
      validation,
      risk,
      gateway: broker,
      order_check: {
        status:
          validation.meta?.order_check_retcode != null ? "checked" : validation.status,
        reason: String(
          validation.meta?.order_check_comment || validation.reason || "—",
        ),
        meta: validation.meta,
      },
      order_send: {
        status: broker.status,
        reason: String(broker.meta?.comment || broker.reason || "—"),
        latency_ms: broker.latency_ms,
        meta: broker.meta,
      },
      request_payload: (meta.request_payload as Record<string, unknown>) || null,
      response_payload: (meta.response_payload as Record<string, unknown>) || null,
    };
  });
}
