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
