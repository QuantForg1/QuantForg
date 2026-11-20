export const PERFORMANCE_LANES = [
  "live",
  "demo",
  "backtest",
  "simulated",
  "unverified",
] as const;

export type PerformanceLane = (typeof PERFORMANCE_LANES)[number];

export type CatalogStrategy = {
  key: string;
  name: string;
  category: string;
  description: string;
};

export type MarketplaceEntry = CatalogStrategy & {
  version: string | null;
  timeframe: string | null;
  instrument: string | null;
  status: string | null;
  releaseNotes: string | null;
  performance: Record<PerformanceLane, "unavailable">;
  combinedPerformance: null;
  salesEnabled: false;
  copyTradingEnabled: false;
};

const EMPTY = "Unavailable";

export function marketplaceEntries(payload: unknown): MarketplaceEntry[] {
  const items = Array.isArray(payload)
    ? payload
    : payload && typeof payload === "object" && Array.isArray((payload as { items?: unknown }).items)
      ? (payload as { items: unknown[] }).items
      : [];
  const entries: MarketplaceEntry[] = [];
  for (const item of items) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const key = text(row.key);
    if (!key) continue;
    entries.push({
      key,
      name: text(row.name) || key,
      category: text(row.category) || EMPTY,
      description: text(row.description) || EMPTY,
      version: text(row.version) || null,
      timeframe: text(row.timeframe) || null,
      instrument: text(row.instrument) || text(row.symbol) || null,
      status: text(row.status) || null,
      releaseNotes: text(row.release_notes) || text(row.releaseNotes) || null,
      performance: {
        live: "unavailable",
        demo: "unavailable",
        backtest: "unavailable",
        simulated: "unavailable",
        unverified: "unavailable",
      },
      combinedPerformance: null,
      salesEnabled: false,
      copyTradingEnabled: false,
    });
  }
  return entries;
}

export function findMarketplaceEntry(
  entries: readonly MarketplaceEntry[],
  key: string,
): MarketplaceEntry | null {
  return entries.find((entry) => entry.key === key) ?? null;
}

export function filterMarketplace(
  entries: readonly MarketplaceEntry[],
  query: string,
  category: string,
): MarketplaceEntry[] {
  const needle = query.trim().toLowerCase();
  return entries.filter((entry) => {
    const categoryMatch = category === "" || entry.category === category;
    if (!categoryMatch) return false;
    if (!needle) return true;
    return (
      entry.name.toLowerCase().includes(needle) ||
      entry.key.toLowerCase().includes(needle) ||
      entry.description.toLowerCase().includes(needle) ||
      (entry.instrument ?? "").toLowerCase().includes(needle)
    );
  });
}

export function displayValue(value: string | null): string {
  return value && value.trim() ? value : "Unavailable";
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}
