/**
 * Bounded last-known-good for authenticated Auto Trading ops telemetry.
 * Never fabricates values. TTL expiry → miss (UNKNOWN / DEGRADED).
 */

const LAST_GOOD_TTL_MS = 5 * 60_000;

type LastGood = {
  payload: Record<string, unknown>;
  at: number;
};

let lastGood: LastGood | null = null;

export function rememberOpsTelemetry(
  payload: unknown,
  now = Date.now(),
): void {
  if (payload == null || typeof payload !== "object" || Array.isArray(payload)) {
    return;
  }
  const record = payload as Record<string, unknown>;
  if (!Object.keys(record).length) return;
  lastGood = { payload: record, at: now };
}

export function readOpsTelemetry(
  now = Date.now(),
): { payload: Record<string, unknown>; stale: boolean } | null {
  if (!lastGood) return null;
  if (now - lastGood.at > LAST_GOOD_TTL_MS) return null;
  return {
    payload: lastGood.payload,
    stale: now - lastGood.at > 15_000,
  };
}

export function resetOpsTelemetryLastGood(): void {
  lastGood = null;
}
