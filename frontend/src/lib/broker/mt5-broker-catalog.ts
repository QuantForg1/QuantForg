/**
 * MT5 broker registry for Broker Accounts.
 *
 * All eight documented brands are customer-selectable for LIVE connection.
 * Operational verification evidence is separate from selectability.
 * Documented candidates are never presented as confirmed servers.
 *
 * Canonical order (do not sort alphabetically):
 * Weltrade → XM → Exness → HFM → JustMarkets → IC Markets → Pepperstone → FP Markets
 */

export type Mt5BrokerSlug =
  | "weltrade"
  | "xm"
  | "exness"
  | "hfm"
  | "justmarkets"
  | "ic-markets"
  | "pepperstone"
  | "fp-markets";

export type Mt5ConnectionStatus =
  | "production_verified"
  | "demo_verified"
  | "live_verified"
  | "owner_verified_live"
  | "not_verified";

export type CustomerConnectionLifecycle =
  | "not_connected"
  | "connecting"
  | "connected"
  | "connection_failed";

const VERIFIED_STATUSES: ReadonlySet<Mt5ConnectionStatus> = new Set([
  "production_verified",
  "demo_verified",
  "live_verified",
  "owner_verified_live",
]);

/** Statuses that may drive operational connectable / trade routing UI. */
const TRADE_CONNECTABLE_STATUSES: ReadonlySet<Mt5ConnectionStatus> = new Set([
  "production_verified",
  "demo_verified",
  "live_verified",
]);

export function isBrokerVerifiedStatus(
  status: string | null | undefined,
): boolean {
  return VERIFIED_STATUSES.has(status as Mt5ConnectionStatus);
}

export function isBrokerTradeConnectableStatus(
  status: string | null | undefined,
): boolean {
  return TRADE_CONNECTABLE_STATUSES.has(status as Mt5ConnectionStatus);
}

/** Primary UI label — never surfaces FUNDING_REQUIRED / OWNER_VERIFIED_LIVE. */
export function brokerVerificationDisplayLabel(
  status: string | null | undefined,
): string {
  if (status === "not_verified" || !status) return "Not verified";
  if (isBrokerVerifiedStatus(status) || status === "VERIFIED_LIVE") {
    return "Verified";
  }
  return "Not verified";
}

export function brokerVerificationStatusCode(
  status: string | null | undefined,
): "VERIFIED_LIVE" | "VERIFIED_DEMO" | "NOT_VERIFIED" {
  if (status === "demo_verified") return "VERIFIED_DEMO";
  if (
    status === "live_verified" ||
    status === "production_verified" ||
    status === "owner_verified_live" ||
    status === "VERIFIED_LIVE"
  ) {
    return "VERIFIED_LIVE";
  }
  return "NOT_VERIFIED";
}

export type Mt5BrokerOption = {
  slug: Mt5BrokerSlug;
  name: string;
  logoSrc: string;
  website: string;
  connectionStatus: Mt5ConnectionStatus;
  /** Operational evidence — not a customer selector gate. */
  connectable: boolean;
  /** Customer may start LIVE connect without prior QuantForg DEMO verify. */
  customerSelectable: boolean;
  /** Seed servers only when already production-proven (Weltrade). */
  servers: {
    live: string[];
    demo: string[];
  };
};

export type Mt5ServerEvidenceClass =
  | "CONFIRMED"
  | "DOCUMENTED"
  | "CANDIDATE"
  | "MANUAL_ACCOUNT_SERVER_REQUIRED";

export type Mt5ServerRow = {
  name: string;
  environment: "demo" | "live" | "unknown";
  source: string;
  verified_at: string | null;
  confirmed?: boolean;
  /** Explicit evidence class — never invent CONFIRMED from naming conventions. */
  evidence_classification?: Mt5ServerEvidenceClass;
};

export const MT5_BROKER_OPTIONS: readonly Mt5BrokerOption[] = [
  {
    slug: "weltrade",
    name: "Weltrade",
    logoSrc: "/brand/brokers/weltrade-mark.png",
    website: "https://www.weltrade.com",
    connectionStatus: "production_verified",
    connectable: true,
    customerSelectable: true,
    servers: {
      live: ["Weltrade-Real"],
      demo: ["Weltrade-Demo"],
    },
  },
  {
    slug: "xm",
    name: "XM",
    logoSrc: "/brand/brokers/xm-mark.png",
    website: "https://www.xm.com",
    connectionStatus: "live_verified",
    connectable: true,
    customerSelectable: true,
    servers: { live: ["XMGlobal-MT5 20"], demo: [] },
  },
  {
    slug: "exness",
    name: "Exness",
    logoSrc: "/brand/brokers/exness-mark.png",
    website: "https://www.exness.com",
    connectionStatus: "live_verified",
    connectable: true,
    customerSelectable: true,
    servers: { live: ["Exness-MT5Real10"], demo: [] },
  },
  {
    slug: "hfm",
    name: "HFM",
    logoSrc: "/brand/brokers/hfm-mark.png",
    website: "https://www.hfm.com",
    connectionStatus: "live_verified",
    connectable: true,
    customerSelectable: true,
    servers: { live: ["HFMarketsGlobal-Live20"], demo: [] },
  },
  {
    slug: "justmarkets",
    name: "JustMarkets",
    logoSrc: "/brand/brokers/justmarkets-mark.png",
    website: "https://justmarkets.com",
    connectionStatus: "live_verified",
    connectable: true,
    customerSelectable: true,
    servers: { live: ["JustMarkets-Live7"], demo: [] },
  },
  {
    slug: "ic-markets",
    name: "IC Markets",
    logoSrc: "/brand/brokers/icmarkets-mark.png",
    website: "https://www.icmarkets.com",
    connectionStatus: "live_verified",
    connectable: true,
    customerSelectable: true,
    servers: { live: ["ICMarketsSC-MT5-3"], demo: [] },
  },
  {
    slug: "pepperstone",
    name: "Pepperstone",
    logoSrc: "/brand/brokers/pepperstone-mark.png",
    website: "https://pepperstone.com",
    connectionStatus: "live_verified",
    connectable: true,
    customerSelectable: true,
    servers: { live: ["PepperstoneKE-MT5-Live01"], demo: [] },
  },
  {
    slug: "fp-markets",
    name: "FP Markets",
    logoSrc: "/brand/brokers/fpmarkets-mark.svg",
    website: "https://www.fpmarkets.com",
    connectionStatus: "live_verified",
    connectable: true,
    customerSelectable: true,
    servers: { live: ["FPMarketsSC-Live"], demo: [] },
  },
] as const;

export function brokerBySlug(slug: string | null | undefined): Mt5BrokerOption | undefined {
  if (!slug) return undefined;
  return MT5_BROKER_OPTIONS.find((b) => b.slug === slug);
}

export function classifyServerEnvironment(
  serverName: string,
  known?: Mt5ServerRow | null,
): "demo" | "live" | "unknown" {
  if (known?.environment === "demo" || known?.environment === "live") {
    return known.environment;
  }
  const s = String(serverName || "")
    .trim()
    .toLowerCase();
  if (!s) return "unknown";
  if (s.includes("demo") || s.includes("trial")) return "demo";
  if (s.includes("real") || s.includes("live")) return "live";
  // Ambiguous names (e.g. XMGlobal-MT5) stay unknown — never invent live from "-mt5".
  return "unknown";
}

export function matchBrokerByServer(server: string | null | undefined): Mt5BrokerOption | undefined {
  const hay = String(server || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "");
  if (!hay) return undefined;
  const patterns: Array<{ slug: Mt5BrokerSlug; needles: string[] }> = [
    { slug: "weltrade", needles: ["weltrade"] },
    { slug: "xm", needles: ["xmglobal", "xm.com", "xmtrading", "xm-"] },
    { slug: "exness", needles: ["exness"] },
    { slug: "hfm", needles: ["hfm", "hfmarkets", "hotforex"] },
    { slug: "justmarkets", needles: ["justmarkets", "justmarketscy"] },
    { slug: "ic-markets", needles: ["icmarkets", "icmarketssc", "icmarketseu"] },
    { slug: "pepperstone", needles: ["pepperstone"] },
    { slug: "fp-markets", needles: ["fpmarkets", "fpmarketsllc"] },
  ];
  for (const row of patterns) {
    if (row.needles.some((n) => hay.includes(n.replace(/\s+/g, "")))) {
      return brokerBySlug(row.slug);
    }
  }
  return undefined;
}

function documentedRows(broker: Mt5BrokerOption | undefined): Mt5ServerRow[] {
  if (!broker) return [];
  const out: Mt5ServerRow[] = [];
  for (const name of broker.servers.live) {
    out.push({
      name,
      environment: "live",
      source: "documented_verified",
      verified_at: broker.connectable ? "documented" : null,
      confirmed: broker.connectable,
      evidence_classification: broker.connectable ? "CONFIRMED" : "DOCUMENTED",
    });
  }
  for (const name of broker.servers.demo) {
    out.push({
      name,
      environment: "demo",
      source: "documented_verified",
      verified_at: broker.connectable ? "documented" : null,
      confirmed: broker.connectable,
      evidence_classification: broker.connectable ? "CONFIRMED" : "DOCUMENTED",
    });
  }
  return out;
}

/**
 * Full server catalogue for a broker (confirmed + optional candidates).
 * Never invent cross-broker names.
 */
export function serverRowsForBroker(
  broker: Mt5BrokerOption | undefined,
  profileServers?: string[],
  apiServers?: Mt5ServerRow[],
  candidateServers?: Mt5ServerRow[],
): Mt5ServerRow[] {
  const byName = new Map<string, Mt5ServerRow>();

  const push = (row: Mt5ServerRow) => {
    const key = row.name.trim();
    if (!key) return;
    const existing = byName.get(key);
    if (!existing) {
      byName.set(key, row);
      return;
    }
    // Prefer confirmed / verified_at evidence over candidates.
    const existingConfirmed = Boolean(existing.confirmed || existing.verified_at);
    const incomingConfirmed = Boolean(row.confirmed || row.verified_at);
    if (!existingConfirmed && incomingConfirmed) {
      byName.set(key, row);
    }
  };

  if (apiServers?.length) {
    for (const row of apiServers) push(row);
  } else {
    for (const row of documentedRows(broker)) push(row);
  }

  for (const row of candidateServers || []) {
    push({
      ...row,
      confirmed: false,
      verified_at: row.verified_at ?? null,
      source: row.source || "documented_candidate",
      evidence_classification: row.evidence_classification || "CANDIDATE",
    });
  }

  for (const raw of profileServers || []) {
    const name = String(raw || "").trim();
    if (!name || byName.has(name)) continue;
    const env = classifyServerEnvironment(name);
    if (env === "unknown") continue;
    push({
      name,
      environment: env,
      source: "weltrade_profile",
      verified_at: null,
      confirmed: false,
      evidence_classification: "CANDIDATE",
    });
  }

  return [...byName.values()].sort((a, b) => {
    const aConf = a.confirmed ? 0 : 1;
    const bConf = b.confirmed ? 0 : 1;
    if (aConf !== bConf) return aConf - bConf;
    if (a.environment !== b.environment) {
      if (a.environment === "live") return -1;
      if (b.environment === "live") return 1;
    }
    return a.name.localeCompare(b.name);
  });
}

export function serversForBroker(
  broker: Mt5BrokerOption | undefined,
  accountType: "demo" | "live",
  profileServers?: string[],
  apiServers?: Mt5ServerRow[],
  candidateServers?: Mt5ServerRow[],
): string[] {
  const rows = serverRowsForBroker(
    broker,
    profileServers,
    apiServers,
    candidateServers,
  );
  const filtered = rows
    .filter((s) => s.environment === accountType || s.environment === "unknown")
    .map((s) => s.name);
  if (filtered.length) return filtered;
  return rows.map((s) => s.name);
}

export function mapRegistryBrokers(apiBrokers: unknown): Mt5BrokerOption[] {
  if (!Array.isArray(apiBrokers) || !apiBrokers.length) {
    return [...MT5_BROKER_OPTIONS];
  }
  const bySlug = new Map(MT5_BROKER_OPTIONS.map((b) => [b.slug, b]));
  const out: Mt5BrokerOption[] = [];
  for (const raw of apiBrokers) {
    if (!raw || typeof raw !== "object") continue;
    const row = raw as Record<string, unknown>;
    const slug = String(row.slug || "") as Mt5BrokerSlug;
    const base = bySlug.get(slug);
    if (!base) continue;
    const rawStatus = String(
      row.connection_status || row.verification_status || "not_verified",
    );
    // Normalize owner_verified_live → live_verified for consistent UI.
    const normalized =
      rawStatus === "owner_verified_live" || rawStatus === "VERIFIED_LIVE"
        ? "live_verified"
        : rawStatus;
    const connectionStatus: Mt5ConnectionStatus = isBrokerVerifiedStatus(normalized)
      ? (normalized as Mt5ConnectionStatus)
      : "not_verified";
    out.push({
      ...base,
      connectionStatus,
      // Never invent trade-connectable from display status alone.
      connectable: row.connectable === true,
      customerSelectable:
        row.customer_selectable === false ? false : true,
    });
  }
  for (const b of MT5_BROKER_OPTIONS) {
    if (!out.some((x) => x.slug === b.slug)) out.push(b);
  }
  // Stable product order for discoverability.
  return [...out].sort((a, b) => {
    const ai = MT5_BROKER_OPTIONS.findIndex((x) => x.slug === a.slug);
    const bi = MT5_BROKER_OPTIONS.findIndex((x) => x.slug === b.slug);
    return ai - bi;
  });
}

export function connectionLifecycleLabel(
  state: CustomerConnectionLifecycle,
): string {
  switch (state) {
    case "connecting":
      return "Connecting";
    case "connected":
      return "Connected";
    case "connection_failed":
      return "Connection Failed";
    default:
      return "Not Connected";
  }
}
