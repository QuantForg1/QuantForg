/**
 * MT5 broker registry for Broker Accounts.
 *
 * Only Weltrade is marked production-verified / connectable until another
 * broker's MT5 connection is proven on a QuantForg Windows gateway/worker.
 * Documented brands may appear in the dropdown, but must not imply a live path.
 */

export type Mt5BrokerSlug =
  | "weltrade"
  | "exness"
  | "ic-markets"
  | "pepperstone"
  | "fp-markets"
  | "hfm"
  | "xm";

export type Mt5ConnectionStatus = "production_verified" | "not_verified";

export type Mt5BrokerOption = {
  slug: Mt5BrokerSlug;
  name: string;
  logoSrc: string;
  website: string;
  connectionStatus: Mt5ConnectionStatus;
  connectable: boolean;
  /** Verified servers only — empty until discovery / production proof. */
  servers: {
    live: string[];
    demo: string[];
  };
};

export type Mt5ServerRow = {
  name: string;
  environment: "demo" | "live";
  source: string;
  verified_at: string | null;
};

export const MT5_BROKER_OPTIONS: readonly Mt5BrokerOption[] = [
  {
    slug: "weltrade",
    name: "Weltrade",
    logoSrc: "/brand/brokers/weltrade-mark.png",
    website: "https://www.weltrade.com",
    connectionStatus: "production_verified",
    connectable: true,
    servers: {
      live: ["Weltrade-Real"],
      demo: ["Weltrade-Demo"],
    },
  },
  {
    slug: "exness",
    name: "Exness",
    logoSrc: "/brand/brokers/exness-mark.png",
    website: "https://www.exness.com",
    connectionStatus: "not_verified",
    connectable: false,
    servers: { live: [], demo: [] },
  },
  {
    slug: "ic-markets",
    name: "IC Markets",
    logoSrc: "/brand/brokers/icmarkets-mark.svg",
    website: "https://www.icmarkets.com",
    connectionStatus: "not_verified",
    connectable: false,
    servers: { live: [], demo: [] },
  },
  {
    slug: "pepperstone",
    name: "Pepperstone",
    logoSrc: "/brand/brokers/pepperstone-mark.png",
    website: "https://pepperstone.com",
    connectionStatus: "not_verified",
    connectable: false,
    servers: { live: [], demo: [] },
  },
  {
    slug: "fp-markets",
    name: "FP Markets",
    logoSrc: "/brand/brokers/fpmarkets-mark.png",
    website: "https://www.fpmarkets.com",
    connectionStatus: "not_verified",
    connectable: false,
    servers: { live: [], demo: [] },
  },
  {
    slug: "hfm",
    name: "HFM",
    logoSrc: "/brand/brokers/hfm-mark.svg",
    website: "https://www.hfm.com",
    connectionStatus: "not_verified",
    connectable: false,
    servers: { live: [], demo: [] },
  },
  {
    slug: "xm",
    name: "XM",
    logoSrc: "/brand/brokers/xm-mark.png",
    website: "https://www.xm.com",
    connectionStatus: "not_verified",
    connectable: false,
    servers: { live: [], demo: [] },
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
  if (s.includes("real") || s.includes("live") || s.includes("-mt5")) return "live";
  // Documented production names without demo token are treated as live only when
  // the catalogue row already classified them; bare guesses stay unknown.
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
    { slug: "exness", needles: ["exness"] },
    { slug: "ic-markets", needles: ["icmarkets", "icmarketssc", "icmarketseu"] },
    { slug: "pepperstone", needles: ["pepperstone"] },
    { slug: "fp-markets", needles: ["fpmarkets", "fpmarketsllc"] },
    { slug: "hfm", needles: ["hfm", "hfmarkets"] },
    { slug: "xm", needles: ["xmglobal", "xm.com", "xmtrading", "xm-"] },
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
    });
  }
  for (const name of broker.servers.demo) {
    out.push({
      name,
      environment: "demo",
      source: "documented_verified",
      verified_at: broker.connectable ? "documented" : null,
    });
  }
  return out;
}

/**
 * Full verified server catalogue for a broker (Demo + Live).
 * Prefer API rows; fall back to documented verified names + profile servers.
 * Never invent cross-broker names.
 */
export function serverRowsForBroker(
  broker: Mt5BrokerOption | undefined,
  profileServers?: string[],
  apiServers?: Mt5ServerRow[],
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
    // Prefer API / verified_at evidence over documented placeholders.
    if (!existing.verified_at && row.verified_at) {
      byName.set(key, row);
    }
  };

  if (apiServers?.length) {
    for (const row of apiServers) push(row);
  } else {
    for (const row of documentedRows(broker)) push(row);
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
    });
  }

  return [...byName.values()].sort((a, b) => {
    if (a.environment !== b.environment) {
      return a.environment === "live" ? -1 : 1;
    }
    return a.name.localeCompare(b.name);
  });
}

export function serversForBroker(
  broker: Mt5BrokerOption | undefined,
  accountType: "demo" | "live",
  profileServers?: string[],
  apiServers?: Mt5ServerRow[],
): string[] {
  const rows = serverRowsForBroker(broker, profileServers, apiServers);
  const filtered = rows
    .filter((s) => s.environment === accountType)
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
    out.push({
      ...base,
      connectionStatus:
        row.connection_status === "production_verified"
          ? "production_verified"
          : "not_verified",
      connectable: Boolean(row.connectable),
    });
  }
  for (const b of MT5_BROKER_OPTIONS) {
    if (!out.some((x) => x.slug === b.slug)) out.push(b);
  }
  return out;
}
