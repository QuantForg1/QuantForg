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

export type StrategyVersionRecord = {
  version: string;
  releasedAt: string;
  releaseNotes: string | null;
  compatibility: string | null;
  status: string | null;
  timeframe: string | null;
  instrument: string | null;
  riskCharacteristics: string | null;
};

export type MarketplaceEntry = CatalogStrategy & {
  version: string | null;
  timeframe: string | null;
  instrument: string | null;
  status: string | null;
  releaseNotes: string | null;
  compatibility: string | null;
  riskCharacteristics: string | null;
  versions: StrategyVersionRecord[];
  performance: Record<PerformanceLane, string>;
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
      compatibility: text(row.compatibility) || null,
      riskCharacteristics:
        text(row.risk_characteristics) || text(row.riskCharacteristics) || null,
      versions: versionRecords(row.versions),
      performance: {
        live: laneLabel(row.performance, "live"),
        demo: laneLabel(row.performance, "demo"),
        backtest: laneLabel(row.performance, "backtest"),
        simulated: laneLabel(row.performance, "simulated"),
        unverified: laneLabel(row.performance, "unverified"),
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

function versionRecords(value: unknown): StrategyVersionRecord[] {
  if (!Array.isArray(value)) return [];
  const records: StrategyVersionRecord[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const version = text(row.version);
    const releasedAt = text(row.released_at) || text(row.releasedAt);
    if (!version || !releasedAt) continue;
    records.push({
      version,
      releasedAt,
      releaseNotes: text(row.release_notes) || text(row.releaseNotes) || null,
      compatibility: text(row.compatibility) || null,
      status: text(row.status) || null,
      timeframe: text(row.timeframe) || null,
      instrument: text(row.instrument) || null,
      riskCharacteristics:
        text(row.risk_characteristics) || text(row.riskCharacteristics) || null,
    });
  }
  return records;
}

function laneLabel(performance: unknown, lane: PerformanceLane): string {
  if (!performance || typeof performance !== "object" || Array.isArray(performance)) {
    return "unavailable";
  }
  const root = performance as Record<string, unknown>;
  const lanes = root.lanes;
  const cell =
    lanes && typeof lanes === "object" && !Array.isArray(lanes)
      ? (lanes as Record<string, unknown>)[lane]
      : root[lane];
  if (!cell || typeof cell !== "object" || Array.isArray(cell)) return "unavailable";
  const record = cell as Record<string, unknown>;
  const traces = Array.isArray(record.records)
    ? record.records.filter((item) => {
        if (!item || typeof item !== "object") return false;
        return text((item as Record<string, unknown>).trace_id).length > 0;
      })
    : [];
  if (record.status !== "available" || traces.length === 0) return "unavailable";
  const summary = text((traces[0] as Record<string, unknown>).summary);
  return summary || "Recorded";
}
