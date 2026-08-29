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

export function mergeCatalogueRows(
  instruments: Record<string, unknown>[],
  opportunityRows: Record<string, unknown>[],
): Record<string, unknown>[] {
  const byKey = new Map<string, Record<string, unknown>>();
  for (const row of opportunityRows) {
    const key = String(
      row.broker_symbol || row.symbol || row.canonical_symbol || "",
    )
      .trim()
      .toUpperCase();
    if (key) byKey.set(key, row);
  }
  if (instruments.length === 0) return [];
  return instruments.map((inst) => {
    const key = String(inst.broker_symbol || inst.canonical_symbol || "")
      .trim()
      .toUpperCase();
    const scored = key ? byKey.get(key) : undefined;
    return scored ? { ...inst, ...scored } : inst;
  });
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
};

export const EMPTY_MARKET_FILTERS: MarketFilterState = {
  q: "",
  assetClass: "ALL",
  session: "ALL",
  regime: "ALL",
  status: "ALL",
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

export function passwordClearedAfterSubmit(password: string, submitted: boolean): string {
  return submitted ? "" : password;
}
