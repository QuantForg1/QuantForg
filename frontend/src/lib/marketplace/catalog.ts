export type CatalogStrategy = {
  key: string;
  name: string;
  category: string;
  description: string;
};

export type MarketplaceEntry = CatalogStrategy & {
  performance: "unavailable";
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
      performance: "unavailable",
      salesEnabled: false,
      copyTradingEnabled: false,
    });
  }
  return entries;
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
      entry.description.toLowerCase().includes(needle)
    );
  });
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}
