/** Trader UX helpers — session-driven labels. Never invent LIVE_BROKER. */

export const LIVE_BROKER = "LIVE_BROKER";

export type ConnectionDisplayState =
  | "CONNECTED"
  | "CONNECTING"
  | "DISCONNECTED"
  | "BROKER_NOT_CONNECTED"
  | "ACCOUNT_SESSION_MISMATCH"
  | "DATA_UNAVAILABLE"
  | "CATALOGUE_UNAVAILABLE"
  | "EMPTY";

export type ConnectionPresentation = {
  state: ConnectionDisplayState;
  label: string;
  tone: "success" | "warning" | "danger" | "neutral";
  health: string;
  maskedLogin: string;
  server: string;
  lastVerified: string | null;
  connected: boolean;
  ownership: "owned" | "none";
  catalogueUnavailable: boolean;
  accountUnavailable: boolean;
  liveBrokerCatalogue: boolean;
};

const TRADER_ERROR_COPY: Record<string, string> = {
  BROKER_NOT_CONNECTED: "Connect your broker account to start.",
  not_connected: "Connect your broker account to start.",
  INVALID_CREDENTIALS: "Broker login or password was not accepted.",
  CONNECTION_FAILED: "Could not verify the broker connection.",
  GATEWAY_UNAVAILABLE: "The broker gateway is temporarily unavailable.",
  ACCOUNT_SESSION_MISMATCH: "Your trading session needs to be reconnected.",
  account_session_mismatch: "Your trading session needs to be reconnected.",
  CATALOGUE_UNAVAILABLE: "Connect or verify your broker and refresh market data.",
};

export function isLiveBrokerCatalogue(session: Record<string, unknown>): boolean {
  return (
    session.catalogue_source === LIVE_BROKER &&
    session.catalogue_unavailable !== true
  );
}

export function sessionOwnership(
  session: Record<string, unknown>,
): "owned" | "none" {
  const raw = String(session.ownership || "").trim().toLowerCase();
  if (raw === "owned" || session.owned === true) return "owned";
  return "none";
}

export function resolveConnectionPresentation(
  session: Record<string, unknown>,
  opts?: { connecting?: boolean },
): ConnectionPresentation {
  const ux = String(session.ux_state || "");
  const broker = String(session.broker || "");
  const connected = broker === "Connected";
  const mismatch =
    ux === "SESSION_MISMATCH" ||
    String(session.session_code || "") === "ACCOUNT_SESSION_MISMATCH";
  const catalogueUnavailable = Boolean(session.catalogue_unavailable) || ux === "CATALOGUE_UNAVAILABLE";
  const accountUnavailable = Boolean(session.account_unavailable);
  const maskedLogin = String(session.account || "—") || "—";
  const server = String(session.server || "—") || "—";
  const lastVerified =
    typeof session.last_verified === "string" && session.last_verified
      ? session.last_verified
      : null;
  const healthRaw = String(session.connection || "");
  const health = mismatch
    ? "Degraded"
    : healthRaw || (connected ? "Healthy" : "Disconnected");
  const ownership = sessionOwnership(session);

  if (!ux && !broker && !opts?.connecting) {
    return {
      state: "DISCONNECTED",
      label: "…",
      tone: "neutral",
      health: "—",
      maskedLogin: "—",
      server: "—",
      lastVerified: null,
      connected: false,
      ownership: "none",
      catalogueUnavailable: true,
      accountUnavailable: true,
      liveBrokerCatalogue: false,
    };
  }

  if (opts?.connecting) {
    return {
      state: "CONNECTING",
      label: "CONNECTING",
      tone: "warning",
      health: "Connecting",
      maskedLogin,
      server,
      lastVerified,
      connected: false,
      ownership: "none",
      catalogueUnavailable: true,
      accountUnavailable: true,
      liveBrokerCatalogue: false,
    };
  }
  if (mismatch) {
    return {
      state: "ACCOUNT_SESSION_MISMATCH",
      label: "ACCOUNT_SESSION_MISMATCH",
      tone: "danger",
      health: "Degraded",
      maskedLogin,
      server,
      lastVerified,
      connected: false,
      ownership: "none",
      catalogueUnavailable: true,
      accountUnavailable: true,
      liveBrokerCatalogue: false,
    };
  }
  if (!connected || ux === "NO_BROKER") {
    return {
      state: "BROKER_NOT_CONNECTED",
      label: "BROKER NOT CONNECTED",
      tone: "danger",
      health: "Disconnected",
      maskedLogin: "—",
      server: server === "—" ? "—" : server,
      lastVerified,
      connected: false,
      ownership: "none",
      catalogueUnavailable: true,
      accountUnavailable: true,
      liveBrokerCatalogue: false,
    };
  }
  if (catalogueUnavailable) {
    return {
      state: "CATALOGUE_UNAVAILABLE",
      label: "CONNECTED",
      tone: "warning",
      health,
      maskedLogin,
      server,
      lastVerified,
      connected: true,
      ownership,
      catalogueUnavailable: true,
      accountUnavailable,
      liveBrokerCatalogue: false,
    };
  }
  return {
    state: "CONNECTED",
    label: "CONNECTED",
    tone: "success",
    health: health || "Healthy",
    maskedLogin,
    server,
    lastVerified,
    connected: true,
    ownership,
    catalogueUnavailable: false,
    accountUnavailable,
    liveBrokerCatalogue: isLiveBrokerCatalogue(session),
  };
}

export function traderFacingErrorMessage(error: {
  code?: string;
  message?: string;
  details?: unknown;
}): string {
  const details =
    error.details && typeof error.details === "object"
      ? (error.details as Record<string, unknown>)
      : {};
  const reason = String(details.reason || "");
  const code = String(error.code || reason || "");
  if (TRADER_ERROR_COPY[code]) return TRADER_ERROR_COPY[code];
  const upper = code.toUpperCase();
  if (TRADER_ERROR_COPY[upper]) return TRADER_ERROR_COPY[upper];
  const msg = String(error.message || "");
  for (const key of Object.keys(TRADER_ERROR_COPY)) {
    if (msg.includes(key) || reason === key) return TRADER_ERROR_COPY[key];
  }
  if (/gateway|traceback|exception|stack|password|token|secret/i.test(msg)) {
    return TRADER_ERROR_COPY.CONNECTION_FAILED;
  }
  return msg || TRADER_ERROR_COPY.CONNECTION_FAILED;
}

export function scoreDisplay(value: unknown): string {
  if (value == null || value === "" || value === "UNKNOWN" || value === "—") {
    return "UNKNOWN";
  }
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n) && value.trim() === String(n)) return String(n);
    if (value.toUpperCase() === "UNKNOWN") return "UNKNOWN";
    return value;
  }
  return "UNKNOWN";
}

export function isValidBrokerSymbol(raw: unknown): boolean {
  const s = String(raw ?? "").trim();
  if (!s) return false;
  const upper = s.toUpperCase();
  if (upper === "UNKNOWN" || upper === "NULL" || upper === "NONE" || s === "—") {
    return false;
  }
  if (s.length > 64) return false;
  return /^[A-Za-z0-9][A-Za-z0-9._/#-]*$/.test(s);
}

export function mergeCatalogueRows(
  instruments: Record<string, unknown>[],
  opportunityRows: Record<string, unknown>[],
): Record<string, unknown>[] {
  const byKey = new Map<string, Record<string, unknown>>();
  for (const row of opportunityRows) {
    const raw = row.broker_symbol || row.symbol || row.canonical_symbol || "";
    if (!isValidBrokerSymbol(raw)) continue;
    const key = String(raw).trim().toUpperCase();
    byKey.set(key, row);
  }
  if (instruments.length === 0) return [];
  const out: Record<string, unknown>[] = [];
  for (const inst of instruments) {
    const raw = inst.broker_symbol || inst.canonical_symbol || inst.symbol || "";
    if (!isValidBrokerSymbol(raw)) continue;
    const key = String(raw).trim().toUpperCase();
    const scored = byKey.get(key);
    out.push(scored ? { ...inst, ...scored } : inst);
  }
  return out;
}

export function marketDataState(row: Record<string, unknown>): string {
  const dq =
    row.data_quality && typeof row.data_quality === "object"
      ? (row.data_quality as Record<string, unknown>)
      : {};
  const raw = String(
    dq.state || row.data_state || row.status || row.market_status || "UNKNOWN",
  )
    .trim()
    .toUpperCase();
  const allowed = new Set([
    "LIVE",
    "STALE",
    "NO_DATA",
    "MARKET_CLOSED",
    "DISABLED",
    "INSUFFICIENT_HISTORY",
    "UNSUPPORTED",
    "ERROR",
    "UNKNOWN",
    "CATALOGUE_UNAVAILABLE",
  ]);
  return allowed.has(raw) ? raw : "UNKNOWN";
}

export const ASSET_CLASS_ORDER = [
  "FOREX",
  "CRYPTO",
  "METALS",
  "INDICES",
  "ENERGY",
  "OTHER",
] as const;

export type CatalogueViewState =
  | "NOT_READY"
  | "UNAVAILABLE"
  | "LIVE_EMPTY"
  | "LIVE_ROWS";

export type RobotDisplayState =
  | "READY"
  | "RUNNING"
  | "PAUSED"
  | "STOPPED"
  | "BLOCKED";

export type MarketFilterState = {
  q: string;
  assetClass: string;
  session: string;
  regime: string;
  status: string;
  freshness: string;
  direction: string;
};

export const EMPTY_MARKET_FILTERS: MarketFilterState = {
  q: "",
  assetClass: "ALL",
  session: "ALL",
  regime: "ALL",
  status: "ALL",
  freshness: "ALL",
  direction: "ALL",
};

/** Unavailable / missing numerics render as em dash — never coerced to 0. */
export function numericDisplay(value: unknown): string {
  if (value == null || value === "" || value === "—" || value === "UNKNOWN") {
    return "—";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : "—";
  }
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n) && value.trim() === String(n)) return String(n);
    if (value.toUpperCase() === "UNKNOWN") return "—";
    return value;
  }
  return "—";
}

export function priceDisplay(value: unknown, digits = 5): string {
  if (value == null || value === "" || value === "—") return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(Math.min(Math.max(digits, 2), 8));
}

export function normalizeAssetClass(raw: unknown): string {
  const v = String(raw ?? "")
    .trim()
    .toUpperCase();
  if (!v || v === "—" || v === "NULL") return "UNKNOWN";
  if (["FOREX", "FX", "CURRENCY", "CURRENCIES"].includes(v)) return "FOREX";
  if (["CRYPTO", "CRYPTOCURRENCY", "CRYPTOCURRENCIES"].includes(v)) return "CRYPTO";
  if (["METALS", "METAL"].includes(v)) return "METALS";
  if (["INDICES", "INDEX"].includes(v)) return "INDICES";
  if (["ENERGY", "ENERGIES"].includes(v)) return "ENERGY";
  if (v === "OTHER") return "OTHER";
  if (v === "UNKNOWN") return "UNKNOWN";
  return v;
}

export function presentAssetClasses(rows: Record<string, unknown>[]): string[] {
  const seen = new Set<string>();
  for (const row of rows) {
    const cls = normalizeAssetClass(row.asset_class);
    if (cls !== "UNKNOWN") seen.add(cls);
  }
  const ordered = ASSET_CLASS_ORDER.filter((cls) => seen.has(cls));
  const extra = [...seen].filter((cls) => !ASSET_CLASS_ORDER.includes(cls as (typeof ASSET_CLASS_ORDER)[number])).sort();
  return [...ordered, ...extra];
}

export function uniqueRowValues(
  rows: Record<string, unknown>[],
  pick: (row: Record<string, unknown>) => string,
): string[] {
  const seen = new Set<string>();
  for (const row of rows) {
    const v = pick(row).trim();
    if (v && v !== "—" && v !== "UNKNOWN") seen.add(v);
  }
  return [...seen].sort();
}

export function rowRegime(row: Record<string, unknown>): string {
  const evidence =
    row.evidence && typeof row.evidence === "object"
      ? (row.evidence as Record<string, unknown>)
      : {};
  return String(evidence.REGIME || row.regime || row.market_regime || "UNKNOWN")
    .trim()
    .toUpperCase() || "UNKNOWN";
}

export function rowSession(row: Record<string, unknown>): string {
  return String(row.session || row.trading_session || "UNKNOWN")
    .trim()
    .toUpperCase() || "UNKNOWN";
}

export function rowDirection(row: Record<string, unknown>): string {
  const dir = String(row.direction || "UNKNOWN").trim().toUpperCase();
  if (dir.includes("BUY")) return "BUY";
  if (dir.includes("SELL")) return "SELL";
  if (dir === "WAIT") return "WAIT";
  return dir || "UNKNOWN";
}

export function instrumentSymbol(row: Record<string, unknown>): string {
  return String(
    row.broker_symbol || row.symbol || row.canonical_symbol || row.code || "",
  ).trim();
}

export function instrumentName(row: Record<string, unknown>): string {
  const name = String(row.description || row.name || row.display_name || "").trim();
  return name || instrumentSymbol(row) || "—";
}

export function catalogueViewState(input: {
  connected: boolean;
  mismatch: boolean;
  liveBrokerSession: boolean;
  catalogueUnavailable: boolean;
  snapshotFetched: boolean;
  snapshotError: boolean;
  catalogueSource?: unknown;
  instrumentCount: number;
}): CatalogueViewState {
  if (input.mismatch || !input.connected) return "UNAVAILABLE";
  if (input.catalogueUnavailable || !input.liveBrokerSession) return "UNAVAILABLE";
  if (input.snapshotError) return "UNAVAILABLE";
  if (!input.snapshotFetched) return "NOT_READY";
  const source = String(input.catalogueSource || "").trim().toUpperCase();
  if (source !== LIVE_BROKER) return "UNAVAILABLE";
  return input.instrumentCount === 0 ? "LIVE_EMPTY" : "LIVE_ROWS";
}

export function filterMarketRows(
  rows: Record<string, unknown>[],
  filters: MarketFilterState,
): Record<string, unknown>[] {
  const q = filters.q.trim().toUpperCase();
  return rows.filter((row) => {
    if (q) {
      const hay = `${instrumentSymbol(row)} ${instrumentName(row)}`.toUpperCase();
      if (!hay.includes(q)) return false;
    }
    if (filters.assetClass !== "ALL") {
      if (normalizeAssetClass(row.asset_class) !== filters.assetClass) return false;
    }
    if (filters.session !== "ALL" && rowSession(row) !== filters.session) return false;
    if (filters.regime !== "ALL" && rowRegime(row) !== filters.regime) return false;
    if (filters.status !== "ALL" && marketDataState(row) !== filters.status) {
      return false;
    }
    if (filters.freshness !== "ALL" && signalFreshness(row) !== filters.freshness) {
      return false;
    }
    if (filters.direction !== "ALL" && signalBoardDirection(row) !== filters.direction) {
      return false;
    }
    return true;
  });
}

export function robotDisplayState(
  session: Record<string, unknown>,
  connection?: ConnectionPresentation,
): RobotDisplayState {
  const view = connection ?? resolveConnectionPresentation(session);
  if (
    view.state === "BROKER_NOT_CONNECTED" ||
    view.state === "ACCOUNT_SESSION_MISMATCH" ||
    view.state === "CONNECTING" ||
    !view.connected
  ) {
    return "BLOCKED";
  }
  const robot = String(session.robot || "").trim().toLowerCase();
  const ux = String(session.ux_state || "").trim().toUpperCase();
  if (robot === "running" || ux === "ROBOT_RUNNING") return "RUNNING";
  if (robot === "paused" || ux === "ROBOT_PAUSED") return "PAUSED";
  if (ux === "ROBOT_READY" || robot === "ready") return "READY";
  if (robot === "stopped" || robot === "disabled") return "STOPPED";
  if (ux === "ATTENTION") return "BLOCKED";
  return "STOPPED";
}

export const RESEARCH_NOT_AUTHORIZATION =
  "RESEARCH · NOT A TRADE AUTHORIZATION";

export const RESEARCH_OPPORTUNITY = "RESEARCH OPPORTUNITY";
export const RESEARCH_SIGNAL = "RESEARCH SIGNAL";

export const SIGNALS_NOT_AUTHORIZATION = RESEARCH_NOT_AUTHORIZATION;

export function passwordClearedAfterSubmit(password: string, submitted: boolean): string {
  return submitted ? "" : password;
}

export type SignalDirectionFilter = "ALL" | "BUY" | "SELL" | "WATCH";

export type SignalSortKey =
  | "strongest"
  | "newest"
  | "confidence"
  | "opportunity"
  | "edge"
  | "risk_reward"
  | "instrument"
  | "asset_class";

export type SignalFilterState = {
  direction: SignalDirectionFilter;
  assetClass: string;
  session: string;
  regime: string;
  confidence: string;
  dataHealth: string;
  age: string;
  freshness: string;
};

export const EMPTY_SIGNAL_FILTERS: SignalFilterState = {
  direction: "ALL",
  assetClass: "ALL",
  session: "ALL",
  regime: "ALL",
  confidence: "ALL",
  dataHealth: "ALL",
  age: "ALL",
  freshness: "ALL",
};

export const MARKET_UNIVERSE_QUERY_KEY = ["market-universe-snapshot"] as const;
export const TRADER_POLL_MS = 15_000;
export const UNIVERSE_POLL_MS = 30_000;
export const EXPLANATION_UNAVAILABLE = "EXPLANATION UNAVAILABLE";

export type SignalAvailability = CatalogueViewState;

export function signalAvailability(
  catalogue: CatalogueViewState,
): SignalAvailability {
  return catalogue;
}

export function signalBoardDirection(row: Record<string, unknown>): string {
  const dir = rowDirection(row);
  if (dir === "WAIT") return "WATCH";
  return dir;
}

export function isActionableDirection(dir: string): boolean {
  return dir === "BUY" || dir === "SELL";
}

function evidenceBag(row: Record<string, unknown>): Record<string, unknown> {
  return row.evidence && typeof row.evidence === "object"
    ? (row.evidence as Record<string, unknown>)
    : {};
}

export function presentField(value: unknown): string {
  if (value == null || value === "") return "Not available";
  const text = String(value).trim();
  if (!text || text === "—" || text.toUpperCase() === "UNKNOWN") {
    return "Not available";
  }
  return text;
}

export function mergeResearchSignalFields(
  rows: Record<string, unknown>[],
  researchSignals: Record<string, unknown>[],
): Record<string, unknown>[] {
  if (researchSignals.length === 0) return rows;
  const byKey = new Map<string, Record<string, unknown>>();
  for (const sig of researchSignals) {
    const key = instrumentSymbol(sig).toUpperCase();
    if (key) byKey.set(key, sig);
  }
  return rows.map((row) => {
    const extra = byKey.get(instrumentSymbol(row).toUpperCase());
    if (!extra) return row;
    return {
      ...row,
      entry_candidate: row.entry_candidate ?? extra.entry_candidate,
      sl_candidate: row.sl_candidate ?? extra.SL_candidate ?? extra.sl_candidate,
      tp_candidate: row.tp_candidate ?? extra.TP_candidate ?? extra.tp_candidate,
      signal_id: row.signal_id ?? extra.signal_id,
      reason: row.reason ?? extra.reason,
    };
  });
}

export function signalTimestamp(row: Record<string, unknown>): string {
  const raw =
    row.timestamp ??
    row.features_as_of ??
    row.market_timestamp ??
    row.data_timestamp ??
    row.as_of;
  return presentField(raw) === "Not available" ? "" : String(raw);
}

export function parseSignalTime(row: Record<string, unknown>): number | null {
  const raw = signalTimestamp(row);
  if (!raw) return null;
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : null;
}

export type SignalAgeBucket = "RECENT" | "STALE" | "UNKNOWN";

export function signalAgeBucket(row: Record<string, unknown>): SignalAgeBucket {
  const ms = parseSignalTime(row);
  if (ms == null) return "UNKNOWN";
  const ageMs = Date.now() - ms;
  if (!Number.isFinite(ageMs) || ageMs < 0) return "UNKNOWN";
  return ageMs <= 15 * 60 * 1000 ? "RECENT" : "STALE";
}

export function signalConfidence(row: Record<string, unknown>): string {
  return presentField(row.confidence_state ?? row.ai_confidence);
}

export function isHighConfidence(row: Record<string, unknown>): boolean {
  return row.qualified_research === true || row.board_status === "QUALIFIED";
}

function numericSortValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

export function filterSignalRows(
  rows: Record<string, unknown>[],
  filters: SignalFilterState,
): Record<string, unknown>[] {
  return rows.filter((row) => {
    const dir = signalBoardDirection(row);
    if (filters.direction !== "ALL" && dir !== filters.direction) return false;
    if (
      filters.assetClass !== "ALL" &&
      normalizeAssetClass(row.asset_class) !== filters.assetClass
    ) {
      return false;
    }
    if (filters.session !== "ALL" && rowSession(row) !== filters.session) {
      return false;
    }
    if (filters.regime !== "ALL" && rowRegime(row) !== filters.regime) {
      return false;
    }
    if (filters.confidence !== "ALL") {
      const conf = String(row.confidence_state || row.ai_confidence || "")
        .trim()
        .toUpperCase();
      if (conf !== filters.confidence) return false;
    }
    if (filters.dataHealth !== "ALL" && marketDataState(row) !== filters.dataHealth) {
      return false;
    }
    if (filters.age !== "ALL" && signalAgeBucket(row) !== filters.age) return false;
    if (filters.freshness !== "ALL" && signalFreshness(row) !== filters.freshness) {
      return false;
    }
    return true;
  });
}

export function sortSignalRows(
  rows: Record<string, unknown>[],
  sort: SignalSortKey,
): Record<string, unknown>[] {
  if (sort === "strongest") return defaultSortedSignals(rows);
  const copy = [...rows];
  const missingLast = (n: number | null): number =>
    n == null ? Number.NEGATIVE_INFINITY : n;
  copy.sort((a, b) => {
    if (sort === "instrument") {
      return instrumentSymbol(a).localeCompare(instrumentSymbol(b));
    }
    if (sort === "asset_class") {
      return normalizeAssetClass(a.asset_class).localeCompare(
        normalizeAssetClass(b.asset_class),
      );
    }
    if (sort === "newest") {
      return (parseSignalTime(b) ?? 0) - (parseSignalTime(a) ?? 0);
    }
    if (sort === "confidence") {
      const av = missingLast(numericSortValue(a.confidence_state ?? a.ai_confidence));
      const bv = missingLast(numericSortValue(b.confidence_state ?? b.ai_confidence));
      if (bv !== av) return bv - av;
      return String(signalConfidence(a)).localeCompare(String(signalConfidence(b)));
    }
    if (sort === "opportunity") {
      return (
        missingLast(numericSortValue(b.opportunity_score ?? b.opportunity)) -
        missingLast(numericSortValue(a.opportunity_score ?? a.opportunity))
      );
    }
    if (sort === "edge") {
      return (
        missingLast(numericSortValue(b.directional_edge ?? b.edge)) -
        missingLast(numericSortValue(a.directional_edge ?? a.edge))
      );
    }
    if (sort === "risk_reward") {
      return (
        missingLast(numericSortValue(b.RR ?? b.rr)) -
        missingLast(numericSortValue(a.RR ?? a.rr))
      );
    }
    return 0;
  });
  return copy;
}

/** Prefer backend research rank when present; never invent a composite. */
export function defaultSortedSignals(
  rows: Record<string, unknown>[],
): Record<string, unknown>[] {
  const hasRank = rows.some(
    (row) => numericSortValue(row.research_rank_score) != null,
  );
  if (!hasRank) return sortSignalRows(rows, "newest");
  const copy = [...rows];
  copy.sort((a, b) => {
    const av = numericSortValue(a.research_rank_score);
    const bv = numericSortValue(b.research_rank_score);
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return bv - av;
  });
  return copy;
}

export type SignalWhyFactor = { label: string; value: string };

const WHY_KEYS: Array<{ key: string; label: string }> = [
  { key: "WHY_THIS_MARKET", label: "Market" },
  { key: "WHY_THIS_DIRECTION", label: "Direction" },
  { key: "WHY_NOW", label: "Timing" },
  { key: "REGIME", label: "Market regime" },
  { key: "MOMENTUM", label: "Momentum" },
  { key: "VOLATILITY", label: "Volatility" },
  { key: "STRUCTURE_EVIDENCE", label: "Structure" },
  { key: "LIQUIDITY_EVIDENCE", label: "Liquidity" },
  { key: "ZONE_EVIDENCE", label: "Zone" },
  { key: "DATA_FRESHNESS", label: "Data quality" },
  { key: "RISK_CONDITIONS", label: "Risk context" },
  { key: "BLOCKERS", label: "Blockers" },
];

export function signalWhyFactors(row: Record<string, unknown>): SignalWhyFactor[] {
  const ev = evidenceBag(row);
  const out: SignalWhyFactor[] = [];
  const reason = presentField(row.reason ?? row.explanation);
  if (reason !== "Not available") {
    out.push({ label: "Why this signal exists", value: reason });
  }
  for (const item of WHY_KEYS) {
    const shown = presentField(ev[item.key]);
    if (shown === "Not available") continue;
    out.push({ label: item.label, value: shown });
  }
  const session = presentField(row.session ?? row.trading_session);
  if (session !== "Not available" && !out.some((f) => f.label === "Session")) {
    out.push({ label: "Session", value: session });
  }
  return out;
}

export type SignalFreshness =
  | "LIVE"
  | "RECENT"
  | "STALE"
  | "PARTIAL"
  | "UNAVAILABLE";

/** Honesty map from existing quality/age fields. Never infers LIVE from page open. */
export function signalFreshness(row: Record<string, unknown>): SignalFreshness {
  const state = marketDataState(row);
  if (
    state === "CATALOGUE_UNAVAILABLE" ||
    state === "ERROR" ||
    state === "NO_DATA" ||
    state === "UNSUPPORTED" ||
    state === "DISABLED"
  ) {
    return "UNAVAILABLE";
  }
  if (state === "STALE") return "STALE";
  if (state === "INSUFFICIENT_HISTORY" || state === "MARKET_CLOSED") return "PARTIAL";
  if (state === "LIVE") {
    return signalAgeBucket(row) === "STALE" ? "STALE" : "LIVE";
  }
  const age = signalAgeBucket(row);
  if (age === "RECENT") return "RECENT";
  if (age === "STALE") return "STALE";
  return "UNAVAILABLE";
}

export function signalStrength(row: Record<string, unknown>): string {
  const rank = numericSortValue(row.research_rank_score);
  if (rank != null) return String(rank);
  const conf = signalConfidence(row);
  if (conf !== "Not available") return conf;
  return "UNKNOWN";
}

export function signalTimestampLabel(row: Record<string, unknown>): string {
  const raw = signalTimestamp(row);
  return raw || "—";
}

export function lastUpdatedCopy(raw: unknown, nowMs = Date.now()): string {
  if (raw == null || raw === "") return "";
  const ms = typeof raw === "number" ? raw : Date.parse(String(raw));
  if (!Number.isFinite(ms)) return "";
  const diffSec = Math.round((nowMs - ms) / 1000);
  if (!Number.isFinite(diffSec) || diffSec < 0) return "";
  if (diffSec < 60) return `Last updated ${diffSec} seconds ago`;
  const mins = Math.round(diffSec / 60);
  if (mins < 60) return `Last updated ${mins} minute${mins === 1 ? "" : "s"} ago`;
  const hrs = Math.round(mins / 60);
  return `Last updated ${hrs} hour${hrs === 1 ? "" : "s"} ago`;
}

export function marketSignalLabel(row: Record<string, unknown>): string {
  const status = presentField(row.board_status || row.setup_state);
  if (status !== "Not available") return status;
  const dir = signalBoardDirection(row);
  if (dir === "BUY" || dir === "SELL") return dir;
  return "UNKNOWN";
}

export function connectionShortLabel(state: ConnectionDisplayState): string {
  if (state === "CONNECTED") return "CONNECTED";
  if (state === "CONNECTING") return "CONNECTING";
  if (state === "ACCOUNT_SESSION_MISMATCH") return "SESSION MISMATCH";
  if (state === "BROKER_NOT_CONNECTED") return "BROKER NOT CONNECTED";
  if (state === "DISCONNECTED") return "DISCONNECTED";
  return "UNAVAILABLE";
}

export function positionExposureLabel(side: unknown): "LONG" | "SHORT" | "—" {
  const raw = positionSideLabel(side);
  if (raw === "BUY") return "LONG";
  if (raw === "SELL") return "SHORT";
  return "—";
}

export function accountHealthSummary(
  items: AccountHealthItem[],
): "Healthy" | "Attention" | "Unavailable" {
  if (items.length === 0) return "Unavailable";
  const states = items.map((item) => item.state);
  if (states.every((s) => s === "Healthy")) return "Healthy";
  if (states.every((s) => s === "Unavailable" || s === "Blocked")) return "Unavailable";
  return "Attention";
}

export type SignalSummary = {
  available: boolean;
  active: string;
  highConfidence: string;
  buy: string;
  sell: string;
  watch: string;
  markets: string;
  assetClasses: string;
  lastUpdate: string;
  strongest: string;
};

function countOrDash(available: boolean, n: number): string {
  return available ? String(n) : "—";
}

export function signalSummary(input: {
  availability: SignalAvailability;
  rows: Record<string, unknown>[];
  instrumentCount: number;
  lastUpdate: unknown;
}): SignalSummary {
  const live =
    input.availability === "LIVE_ROWS" || input.availability === "LIVE_EMPTY";
  if (!live) {
    return {
      available: false,
      active: "—",
      highConfidence: "—",
      buy: "—",
      sell: "—",
      watch: "—",
      markets: "—",
      assetClasses: "—",
      lastUpdate:
        presentField(input.lastUpdate) === "Not available"
          ? "—"
          : String(input.lastUpdate),
      strongest: "—",
    };
  }
  const dirs = input.rows.map(signalBoardDirection);
  return {
    available: true,
    active: countOrDash(true, dirs.filter(isActionableDirection).length),
    highConfidence: countOrDash(true, input.rows.filter(isHighConfidence).length),
    buy: countOrDash(true, dirs.filter((d) => d === "BUY").length),
    sell: countOrDash(true, dirs.filter((d) => d === "SELL").length),
    watch: countOrDash(true, dirs.filter((d) => d === "WATCH").length),
    markets: countOrDash(true, input.instrumentCount),
    assetClasses: countOrDash(true, presentAssetClasses(input.rows).length),
    lastUpdate:
      presentField(input.lastUpdate) === "Not available"
        ? "—"
        : String(input.lastUpdate),
    strongest: strongestSetupLabel(input.rows, input.availability),
  };
}

export function strongestSetupLabel(
  rows: Record<string, unknown>[],
  availability: SignalAvailability,
): string {
  if (availability !== "LIVE_ROWS") return "—";
  const top = defaultSortedSignals(rows).find((row) =>
    isActionableDirection(signalBoardDirection(row)),
  );
  if (!top) return "—";
  const symbol = instrumentSymbol(top);
  const dir = signalBoardDirection(top);
  return symbol ? `${symbol} ${dir}` : "—";
}

export function topResearchOpportunities(
  rows: Record<string, unknown>[],
  availability: SignalAvailability,
  limit = 4,
): Record<string, unknown>[] {
  if (availability !== "LIVE_ROWS" || limit <= 0) return [];
  return defaultSortedSignals(rows)
    .filter((row) => isActionableDirection(signalBoardDirection(row)))
    .slice(0, limit);
}

export type SignalFeedState =
  | "LOADING"
  | "DISCONNECTED"
  | "MISMATCH"
  | "CATALOGUE_UNAVAILABLE"
  | "ERROR"
  | "EMPTY"
  | "STALE"
  | "PARTIAL"
  | "LIVE";

export function signalFeedState(input: {
  loading: boolean;
  noBroker: boolean;
  mismatch: boolean;
  snapshotError: boolean;
  availability: SignalAvailability;
  rows: Record<string, unknown>[];
}): SignalFeedState {
  if (input.noBroker) return "DISCONNECTED";
  if (input.mismatch) return "MISMATCH";
  if (input.snapshotError) return "ERROR";
  if (input.availability === "UNAVAILABLE") return "CATALOGUE_UNAVAILABLE";
  if (input.loading || input.availability === "NOT_READY") return "LOADING";
  if (input.availability === "LIVE_EMPTY") return "EMPTY";
  const states = input.rows.map((row) => marketDataState(row));
  const live = states.filter((s) => s === "LIVE").length;
  const stale = states.filter((s) => s === "STALE").length;
  if (stale > 0 && live === 0) return "STALE";
  if (stale > 0 || states.some((s) => s === "ERROR" || s === "NO_DATA")) return "PARTIAL";
  return "LIVE";
}

export function signalFeedStateLabel(state: SignalFeedState): string {
  if (state === "DISCONNECTED") return "BROKER NOT CONNECTED";
  if (state === "MISMATCH") return "ACCOUNT_SESSION_MISMATCH";
  if (state === "CATALOGUE_UNAVAILABLE") return "CATALOGUE UNAVAILABLE";
  if (state === "ERROR") return "ERROR";
  if (state === "EMPTY") return "NO SIGNALS";
  if (state === "STALE") return "STALE DATA";
  if (state === "PARTIAL") return "PARTIAL DATA";
  if (state === "LOADING") return "LOADING";
  return "LIVE";
}

export function unavailableSignalsTitle(reason: {
  noBroker?: boolean;
  mismatch?: boolean;
  catalogue?: CatalogueViewState;
}): { title: string; description: string } {
  if (reason.noBroker) {
    return {
      title: "SIGNALS UNAVAILABLE",
      description:
        "BROKER NOT CONNECTED. Connect and verify your broker to load live market intelligence.",
    };
  }
  if (reason.mismatch) {
    return {
      title: "SIGNALS UNAVAILABLE",
      description: "ACCOUNT SESSION MISMATCH. Reconnect your own broker account.",
    };
  }
  if (reason.catalogue === "UNAVAILABLE") {
    return {
      title: "SIGNALS UNAVAILABLE",
      description:
        "Market intelligence is currently unavailable. This is not zero signals.",
    };
  }
  return {
    title: "SIGNALS UNAVAILABLE",
    description: "Live signal data is not available for this account.",
  };
}

export function dataSourceLabel(input: {
  liveBroker: boolean;
  catalogueSource: unknown;
}): string {
  const source = String(input.catalogueSource || "").trim().toUpperCase();
  if (input.liveBroker && source === "LIVE_BROKER") {
    return "Broker catalogue";
  }
  if (source === "UNAVAILABLE" || source === "CATALOGUE_UNAVAILABLE") {
    return "CATALOGUE UNAVAILABLE";
  }
  if (!source) return "UNAVAILABLE";
  return "UNAVAILABLE";
}

export type HealthTone = "Healthy" | "Attention" | "Unavailable" | "Blocked";

export type AccountHealthItem = {
  id: string;
  label: string;
  state: HealthTone;
  detail: string;
};

export function moneyDisplay(value: unknown, available: boolean): string {
  if (!available) return "—";
  return numericDisplay(value);
}

export function positionSideLabel(side: unknown): string {
  const raw = String(side || "")
    .trim()
    .toUpperCase();
  if (raw === "BUY" || raw === "LONG") return "BUY";
  if (raw === "SELL" || raw === "SHORT") return "SELL";
  return raw || "—";
}

export function portfolioAccount(
  payload: Record<string, unknown>,
): Record<string, unknown> {
  const nested = payload.account;
  if (nested && typeof nested === "object") {
    return nested as Record<string, unknown>;
  }
  return payload;
}

export function accountHealth(input: {
  connection: ConnectionPresentation;
  robot: RobotDisplayState;
  liveCatalogue: boolean;
  positionsError: boolean;
  positionsLoaded: boolean;
  marginAvailable: boolean;
  accountUnavailable: boolean;
}): AccountHealthItem[] {
  const broker: AccountHealthItem = (() => {
    if (input.connection.state === "CONNECTED") {
      return {
        id: "broker",
        label: "Broker connection",
        state: "Healthy",
        detail: input.connection.label,
      };
    }
    if (
      input.connection.state === "CONNECTING" ||
      input.connection.state === "CATALOGUE_UNAVAILABLE"
    ) {
      return {
        id: "broker",
        label: "Broker connection",
        state: "Attention",
        detail: input.connection.label,
      };
    }
    if (
      input.connection.state === "BROKER_NOT_CONNECTED" ||
      input.connection.state === "ACCOUNT_SESSION_MISMATCH"
    ) {
      return {
        id: "broker",
        label: "Broker connection",
        state: "Blocked",
        detail: input.connection.label,
      };
    }
    return {
      id: "broker",
      label: "Broker connection",
      state: "Unavailable",
      detail: input.connection.label || "—",
    };
  })();

  const market: AccountHealthItem = (() => {
    if (
      input.connection.state === "BROKER_NOT_CONNECTED" ||
      input.connection.state === "ACCOUNT_SESSION_MISMATCH"
    ) {
      return {
        id: "market",
        label: "Market data",
        state: "Blocked",
        detail: input.connection.label,
      };
    }
    if (input.liveCatalogue) {
      return { id: "market", label: "Market data", state: "Healthy", detail: "Broker catalogue" };
    }
    if (input.connection.catalogueUnavailable) {
      return {
        id: "market",
        label: "Market data",
        state: "Unavailable",
        detail: "CATALOGUE UNAVAILABLE",
      };
    }
    return { id: "market", label: "Market data", state: "Unavailable", detail: "—" };
  })();

  const execution: AccountHealthItem = (() => {
    if (input.connection.state === "ACCOUNT_SESSION_MISMATCH") {
      return {
        id: "execution",
        label: "Execution readiness",
        state: "Blocked",
        detail: "ACCOUNT_SESSION_MISMATCH",
      };
    }
    if (input.connection.state === "BROKER_NOT_CONNECTED") {
      return {
        id: "execution",
        label: "Execution readiness",
        state: "Blocked",
        detail: "BROKER NOT CONNECTED",
      };
    }
    if (input.connection.connected && input.connection.ownership === "owned") {
      return {
        id: "execution",
        label: "Execution readiness",
        state: "Healthy",
        detail: "Owned session",
      };
    }
    if (input.connection.connected) {
      return {
        id: "execution",
        label: "Execution readiness",
        state: "Attention",
        detail: "Ownership unverified",
      };
    }
    return {
      id: "execution",
      label: "Execution readiness",
      state: "Unavailable",
      detail: "—",
    };
  })();

  const margin: AccountHealthItem = (() => {
    if (input.accountUnavailable || !input.marginAvailable) {
      return { id: "margin", label: "Margin", state: "Unavailable", detail: "—" };
    }
    if (!input.connection.connected) {
      return {
        id: "margin",
        label: "Margin",
        state: "Blocked",
        detail: "BROKER NOT CONNECTED",
      };
    }
    return { id: "margin", label: "Margin", state: "Healthy", detail: "Reported by broker" };
  })();

  const positions: AccountHealthItem = (() => {
    if (
      input.connection.state === "BROKER_NOT_CONNECTED" ||
      input.connection.state === "ACCOUNT_SESSION_MISMATCH"
    ) {
      return {
        id: "positions",
        label: "Positions",
        state: "Blocked",
        detail: input.connection.label,
      };
    }
    if (input.positionsError) {
      return {
        id: "positions",
        label: "Positions",
        state: "Unavailable",
        detail: "POSITIONS UNAVAILABLE",
      };
    }
    if (!input.positionsLoaded) {
      return { id: "positions", label: "Positions", state: "Unavailable", detail: "—" };
    }
    return {
      id: "positions",
      label: "Positions",
      state: "Healthy",
      detail: "Account positions loaded",
    };
  })();

  const robot: AccountHealthItem = (() => {
    if (input.robot === "RUNNING" || input.robot === "READY") {
      return { id: "robot", label: "Robot status", state: "Healthy", detail: input.robot };
    }
    if (input.robot === "PAUSED" || input.robot === "STOPPED") {
      return { id: "robot", label: "Robot status", state: "Attention", detail: input.robot };
    }
    return { id: "robot", label: "Robot status", state: "Blocked", detail: input.robot };
  })();

  return [broker, market, execution, margin, positions, robot];
}

export function periodPnl(
  deals: Record<string, unknown>[],
  sinceMs: number,
): string {
  if (!Array.isArray(deals)) return "—";
  let sum = 0;
  let counted = 0;
  for (const deal of deals) {
    const t = Date.parse(String(deal.time || deal.closed_at || deal.opened_at || ""));
    if (!Number.isFinite(t) || t < sinceMs) continue;
    const pnl = Number(deal.profit);
    if (!Number.isFinite(pnl)) continue;
    sum += pnl;
    counted += 1;
  }
  if (counted === 0) return "—";
  return String(sum);
}

export const CLOSED_TRADE_MIN_SAMPLE = 5;
export const INSUFFICIENT_SAMPLE = "INSUFFICIENT SAMPLE";

export type ClosedTradeStats = {
  status: "UNAVAILABLE" | "INSUFFICIENT_SAMPLE" | "READY";
  realized: string;
  sample: string;
  winRate: string;
  profitFactor: string;
  drawdown: string;
};

export function closedTradeStats(
  deals: Record<string, unknown>[],
  available: boolean,
): ClosedTradeStats {
  if (!available) {
    return {
      status: "UNAVAILABLE",
      realized: "—",
      sample: "—",
      winRate: "—",
      profitFactor: "—",
      drawdown: "—",
    };
  }
  const pnls: number[] = [];
  for (const deal of deals) {
    const pnl = Number(deal.profit);
    if (Number.isFinite(pnl)) pnls.push(pnl);
  }
  if (pnls.length === 0) {
    return {
      status: "INSUFFICIENT_SAMPLE",
      realized: INSUFFICIENT_SAMPLE,
      sample: INSUFFICIENT_SAMPLE,
      winRate: INSUFFICIENT_SAMPLE,
      profitFactor: INSUFFICIENT_SAMPLE,
      drawdown: INSUFFICIENT_SAMPLE,
    };
  }
  const realized = String(pnls.reduce((a, b) => a + b, 0));
  if (pnls.length < CLOSED_TRADE_MIN_SAMPLE) {
    return {
      status: "INSUFFICIENT_SAMPLE",
      realized,
      sample: String(pnls.length),
      winRate: INSUFFICIENT_SAMPLE,
      profitFactor: INSUFFICIENT_SAMPLE,
      drawdown: INSUFFICIENT_SAMPLE,
    };
  }
  const wins = pnls.filter((p) => p > 0);
  const losses = pnls.filter((p) => p < 0);
  const grossWin = wins.reduce((a, b) => a + b, 0);
  const grossLoss = Math.abs(losses.reduce((a, b) => a + b, 0));
  return {
    status: "READY",
    realized,
    sample: String(pnls.length),
    winRate: `${((wins.length / pnls.length) * 100).toFixed(1)}%`,
    profitFactor:
      grossLoss === 0 ? INSUFFICIENT_SAMPLE : (grossWin / grossLoss).toFixed(2),
    drawdown: INSUFFICIENT_SAMPLE,
  };
}

export function exposureUnavailableReason(): string {
  return "EXPOSURE DATA UNAVAILABLE";
}
