/**
 * Documented MT5 broker brands for Broker Accounts UI.
 * Connection still uses the existing MT5 / Weltrade session path —
 * this catalog only drives selection labels, logos, and server hints.
 */

export type Mt5BrokerSlug =
  | "weltrade"
  | "exness"
  | "ic-markets"
  | "pepperstone"
  | "fp-markets"
  | "hfm"
  | "xm";

export type Mt5BrokerOption = {
  slug: Mt5BrokerSlug;
  name: string;
  logoSrc: string;
  website: string;
  /** Documented server name hints — never invent beyond these UI options. */
  servers: {
    live: string[];
    demo: string[];
  };
};

export const MT5_BROKER_OPTIONS: readonly Mt5BrokerOption[] = [
  {
    slug: "weltrade",
    name: "Weltrade",
    logoSrc: "/brand/brokers/weltrade-mark.png",
    website: "https://www.weltrade.com",
    servers: {
      live: ["Weltrade-Real", "Weltrade-MT5"],
      demo: ["Weltrade-Demo"],
    },
  },
  {
    slug: "exness",
    name: "Exness",
    logoSrc: "/brand/brokers/exness-mark.png",
    website: "https://www.exness.com",
    servers: {
      live: ["Exness-MT5Real", "Exness-MT5"],
      demo: ["Exness-Trial"],
    },
  },
  {
    slug: "ic-markets",
    name: "IC Markets",
    logoSrc: "/brand/brokers/icmarkets-mark.svg",
    website: "https://www.icmarkets.com",
    servers: {
      live: ["ICMarketsSC-MT5", "ICMarketsSC-MT5-2", "ICMarketsEU-MT5"],
      demo: ["ICMarkets-Demo"],
    },
  },
  {
    slug: "pepperstone",
    name: "Pepperstone",
    logoSrc: "/brand/brokers/pepperstone-mark.png",
    website: "https://pepperstone.com",
    servers: {
      live: ["Pepperstone-MT5-Live", "PepperstoneLtd-Live"],
      demo: ["Pepperstone-MT5-Demo"],
    },
  },
  {
    slug: "fp-markets",
    name: "FP Markets",
    logoSrc: "/brand/brokers/fpmarkets-mark.png",
    website: "https://www.fpmarkets.com",
    servers: {
      live: ["FPMarkets-Live", "FPMarketsLLC-Live"],
      demo: ["FPMarkets-Demo"],
    },
  },
  {
    slug: "hfm",
    name: "HFM",
    logoSrc: "/brand/brokers/hfm-mark.svg",
    website: "https://www.hfm.com",
    servers: {
      live: ["HFM-Live", "HFMarketsGlobal-Live"],
      demo: ["HFM-Demo"],
    },
  },
  {
    slug: "xm",
    name: "XM",
    logoSrc: "/brand/brokers/xm-mark.png",
    website: "https://www.xm.com",
    servers: {
      live: ["XMGlobal-MT5", "XMGlobal-Real", "XM.COM-Real", "XMTrading-Real"],
      demo: ["XMGlobal-Demo"],
    },
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
): string[] {
  const documented = broker
    ? accountType === "demo"
      ? [...broker.servers.demo]
      : [...broker.servers.live]
    : [];
  const merged = [...documented];
  for (const s of profileServers || []) {
    if (s && !merged.includes(s)) merged.push(s);
  }
  return merged.length ? merged : accountType === "demo" ? ["Demo"] : ["Live"];
}
