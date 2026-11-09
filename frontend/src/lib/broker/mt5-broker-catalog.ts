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

export function serversForBroker(
  broker: Mt5BrokerOption | undefined,
  accountType: "demo" | "live",
  profileServers?: string[],
  apiServers?: Mt5ServerRow[],
): string[] {
  if (apiServers && apiServers.length) {
    const filtered = apiServers
      .filter((s) => (accountType === "demo" ? s.environment === "demo" : s.environment === "live"))
      .map((s) => s.name);
    if (filtered.length) return filtered;
    // If API returned mixed envs only, still surface all verified names.
    return apiServers.map((s) => s.name);
  }
  const documented = broker
    ? accountType === "demo"
      ? [...broker.servers.demo]
      : [...broker.servers.live]
    : [];
  const merged = [...documented];
  for (const s of profileServers || []) {
    if (s && !merged.includes(s)) merged.push(s);
  }
  return merged;
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
