/** Safe accessors for loosely typed API payloads (Record / unknown[]). */

export function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export function asList(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  const rec = asRecord(value);
  if (Array.isArray(rec.items)) return rec.items;
  if (Array.isArray(rec.results)) return rec.results;
  if (Array.isArray(rec.data)) return rec.data;
  return [];
}

export function num(value: unknown, fallback = NaN): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return fallback;
}

export function str(value: unknown, fallback = "—"): string {
  if (value == null || value === "") return fallback;
  return String(value);
}

export function bool(value: unknown): boolean {
  return Boolean(value);
}

export function toneFromNumber(value: number): "up" | "down" | "neutral" {
  if (!Number.isFinite(value) || value === 0) return "neutral";
  return value > 0 ? "up" : "down";
}

export function mapEquityCurve(raw: unknown): { t: string; equity: number }[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((point, idx) => {
      if (typeof point === "number") {
        return { t: String(idx + 1), equity: point };
      }
      const p = asRecord(point);
      const equity = num(p.equity ?? p.value ?? p.y ?? p.balance);
      if (!Number.isFinite(equity)) return null;
      const rawT = p.t ?? p.ts ?? p.time ?? p.timestamp ?? p.label ?? idx + 1;
      const t =
        typeof rawT === "string" && rawT.includes("T")
          ? rawT.slice(5, 16).replace("T", " ")
          : str(rawT, String(idx + 1));
      return { t, equity };
    })
    .filter((p): p is { t: string; equity: number } => p != null);
}

export function metric(obj: Record<string, unknown>, ...keys: string[]): number {
  for (const key of keys) {
    const n = num(obj[key]);
    if (Number.isFinite(n)) return n;
  }
  return NaN;
}
