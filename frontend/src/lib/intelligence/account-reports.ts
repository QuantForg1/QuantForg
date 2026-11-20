/** Display helpers for read-only account reports. Missing values stay unavailable. */

export const RELIABILITY_COMPONENTS = [
  "backend",
  "database",
  "authentication",
  "gateway",
  "mt5",
  "broker",
  "data",
  "worker",
] as const;

const RELIABILITY_STATES = new Set([
  "healthy",
  "degraded",
  "disconnected",
  "delayed",
  "unavailable",
  "unknown",
]);

export const COACH_QUESTIONS = [
  { id: "open_risk", label: "Open risk" },
  { id: "week_pnl", label: "Week result" },
  { id: "largest_loss", label: "Largest loss" },
  { id: "last_rejection", label: "Last rejection" },
  { id: "broker_health", label: "Broker session" },
] as const;

export function figureText(value: unknown): string {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (!value || typeof value !== "object" || Array.isArray(value)) return "Unavailable";
  const record = value as Record<string, unknown>;
  const inner = record.value;
  if (inner === null || inner === undefined || inner === "") {
    const status = typeof record.status === "string" ? record.status.trim() : "";
    return status ? status.replaceAll("_", " ") : "Unavailable";
  }
  return figureText(inner);
}

export function reliabilityLabel(report: unknown, name: string): string {
  if (!report || typeof report !== "object") return "Unknown";
  const components = (report as { components?: unknown }).components;
  if (!Array.isArray(components)) return "Unknown";
  const match = components.find((item) => {
    if (!item || typeof item !== "object") return false;
    return (item as { name?: unknown }).name === name;
  }) as { state?: unknown } | undefined;
  const state = typeof match?.state === "string" ? match.state.trim().toLowerCase() : "";
  if (!RELIABILITY_STATES.has(state)) return "Unknown";
  return state;
}

export function coachAnswerText(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "Unavailable";
  const record = payload as { status?: unknown; answer?: unknown };
  if (record.status !== "grounded") return "Unavailable";
  return figureText(record.answer);
}
