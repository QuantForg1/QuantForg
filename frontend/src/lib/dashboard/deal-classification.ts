/**
 * Classify MT5 history rows so deposits/withdrawals never masquerade as trades
 * or OMS execution results.
 */

export type DealKind =
  | "trade"
  | "deposit"
  | "withdrawal"
  | "balance"
  | "other";

/** Local accessors keep this module runnable under node --experimental-strip-types. */
function num(value: unknown, fallback = NaN): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return fallback;
}

function str(value: unknown, fallback = "—"): string {
  if (value == null || value === "") return fallback;
  if (typeof value === "object") return fallback;
  return String(value);
}

const BALANCE_TYPE =
  /\b(balance|credit|charge|correction|bonus|commission|deposit|withdraw(?:al)?|transfer|so_compensation)\b/i;

const BALANCE_COMMENT =
  /\b(deposit|withdraw(?:al)?|balance|credit|bonus|transfer|adjustment|from\s*#)\b/i;

function haystack(deal: Record<string, unknown>): string {
  return [
    deal.deal_type,
    deal.type,
    deal.entry,
    deal.action,
    deal.comment,
    deal.reason,
    deal.status,
    deal.description,
  ]
    .map((v) => str(v, ""))
    .join(" ")
    .toLowerCase();
}

/** Classify a history row without inventing trade semantics. */
export function classifyDealKind(deal: Record<string, unknown>): DealKind {
  const text = haystack(deal);
  const typ = str(deal.deal_type || deal.type, "").toLowerCase();
  const comment = str(deal.comment ?? deal.reason ?? deal.status, "").toLowerCase();
  const symbol = str(deal.symbol, "").trim();

  if (/\bwithdraw/.test(text)) return "withdrawal";
  if (/\bdeposit\b/.test(text) || /deposit from/.test(comment)) return "deposit";
  if (
    BALANCE_TYPE.test(typ) ||
    BALANCE_COMMENT.test(comment) ||
    (!symbol && BALANCE_TYPE.test(text))
  ) {
    return "balance";
  }

  const looksTradeType =
    /\b(buy|sell|deal|trade)\b/.test(typ) ||
    /\b(buy|sell)\b/.test(text);
  if (symbol || looksTradeType) return "trade";

  // Profit-only rows with no symbol/type are not trusted as trades.
  if (!symbol && Number.isFinite(num(deal.profit))) return "balance";
  return "other";
}

/** True only for genuine trading deals used in performance metrics. */
export function isTradeDeal(deal: Record<string, unknown>): boolean {
  return classifyDealKind(deal) === "trade";
}

export function dealTimeMs(deal: Record<string, unknown>): number {
  return Date.parse(str(deal.time ?? deal.close_time ?? deal.deal_time, ""));
}

export function sortDealsNewestFirst(
  deals: Record<string, unknown>[],
): Record<string, unknown>[] {
  return [...deals].sort((a, b) => {
    const ta = dealTimeMs(a);
    const tb = dealTimeMs(b);
    const aOk = Number.isFinite(ta);
    const bOk = Number.isFinite(tb);
    if (aOk && bOk) return tb - ta;
    if (aOk) return -1;
    if (bOk) return 1;
    return 0;
  });
}

/** Newest genuine trade deal, if any. */
export function latestTradeDeal(
  deals: Record<string, unknown>[],
): Record<string, unknown> | null {
  const trades = sortDealsNewestFirst(deals.filter(isTradeDeal));
  return trades[0] ?? null;
}

const STALE_EXECUTION_MS = 7 * 86_400_000;

export type LastExecutionView = {
  attemptLabel: string;
  resultLabel: string;
  stale: boolean;
  source: "oms" | "trade_deal" | "none";
};

/**
 * Prefer OMS/session execution fields. Never fall back to deposits/balance rows.
 */
export function resolveLastExecutionView(opts: {
  sessionExecutionAt?: unknown;
  sessionExecutionResult?: unknown;
  robotExecutionAt?: unknown;
  robotExecutionResult?: unknown;
  deals: Record<string, unknown>[];
  now?: number;
}): LastExecutionView {
  const now = opts.now ?? Date.now();
  const omsAt = str(opts.sessionExecutionAt ?? opts.robotExecutionAt, "");
  const omsResult = str(
    opts.sessionExecutionResult ?? opts.robotExecutionResult,
    "",
  );
  const omsAtMs = Date.parse(omsAt);

  if (omsResult || (omsAt && Number.isFinite(omsAtMs))) {
    const stale = Number.isFinite(omsAtMs) && now - omsAtMs > STALE_EXECUTION_MS;
    return {
      attemptLabel: omsAt || "Time unavailable",
      resultLabel: omsResult || "Result unavailable",
      stale,
      source: "oms",
    };
  }

  const trade = latestTradeDeal(opts.deals);
  if (!trade) {
    return {
      attemptLabel: "No trade execution recorded",
      resultLabel: "—",
      stale: false,
      source: "none",
    };
  }

  const at = str(trade.time ?? trade.close_time, "");
  const atMs = Date.parse(at);
  const stale = Number.isFinite(atMs) && now - atMs > STALE_EXECUTION_MS;
  const side = str(trade.side ?? trade.type ?? trade.deal_type, "trade");
  const symbol = str(trade.symbol, "—");
  const result = str(
    trade.status ?? trade.comment,
    `${symbol} ${side}`.trim(),
  );
  return {
    attemptLabel: at || "Time unavailable",
    resultLabel: result,
    stale,
    source: "trade_deal",
  };
}

export function activityKindFromDeal(
  deal: Record<string, unknown>,
): "closed" | "rejected" | "balance" | "deposit" | "withdrawal" {
  const kind = classifyDealKind(deal);
  if (kind === "deposit") return "deposit";
  if (kind === "withdrawal") return "withdrawal";
  if (kind === "balance" || kind === "other") return "balance";
  const rejected = /reject|denied|blocked/i.test(
    str(deal.status ?? deal.comment ?? deal.reason, ""),
  );
  return rejected ? "rejected" : "closed";
}
