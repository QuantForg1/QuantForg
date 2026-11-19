/** Pure formatting helpers for the Intelligence desks (unit-tested). */

export function formatPrice(v: number): string {
  if (!Number.isFinite(v)) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** "2026-11-19T19:22:43+00:00" → "19:22 UTC" (plus local time when it differs). */
export function formatUtcTime(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  const d = new Date(t);
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${hh}:${mm} UTC`;
}

export function minutesUntil(iso: string, now: number): number {
  const t = Date.parse(iso);
  return Number.isFinite(t) ? (t - now) / 60_000 : Number.NaN;
}

export function relativeTime(iso: string, now: number): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "time not supplied";
  const mins = Math.round((now - t) / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const h = Math.round(mins / 60);
  if (h < 24) return `${h} h ago`;
  return `${Math.round(h / 24)} d ago`;
}

export function impactTone(impact: string): "danger" | "warning" | "neutral" {
  const v = impact.trim().toLowerCase();
  if (["high", "3", "red"].includes(v)) return "danger";
  if (["medium", "moderate", "2", "orange"].includes(v)) return "warning";
  return "neutral";
}

export function biasTone(direction: string): "success" | "danger" | "neutral" {
  if (direction === "bullish") return "success";
  if (direction === "bearish") return "danger";
  return "neutral";
}

/** Map live bias + volatility to the Strategy Lab regime vocabulary. */
export function regimeLabels(
  bias: Record<string, unknown>,
  vol: Record<string, unknown>,
): string[] {
  const out: string[] = [];
  const dir = String(bias.direction ?? "");
  const aligned = Number(bias.aligned ?? 0);
  const of = Number(bias.of ?? 0);
  if (of > 0) {
    out.push((dir === "bullish" || dir === "bearish") && aligned === of ? "Trending" : "Range / mixed");
  }
  const state = String(vol.state ?? "");
  if (state === "high") out.push("High Volatility");
  if (state === "low") out.push("Low Volatility");
  return out;
}

export function strategyFit(bestRegimes: string[], current: string[]): number {
  return bestRegimes.filter((r) => current.includes(r)).length;
}

export function formatCountdown(mins: number): string {
  if (!Number.isFinite(mins)) return "—";
  const total = Math.max(0, Math.round(mins));
  if (total < 60) return `${total} min`;
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h < 24) return m ? `${h} h ${m} min` : `${h} h`;
  return `${Math.floor(h / 24)} d ${h % 24} h`;
}
