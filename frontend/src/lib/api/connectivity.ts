/**
 * Frontend ↔ API reachability (presentation signal only).
 * Updated by apiFetch + optional health probe; consumed by OfflineBanner.
 *
 * Production rule: a single slow/timeout request must NOT mark the whole
 * platform Offline. Require consecutive failures (hysteresis). Timeouts are
 * soft (degraded); true network failures are hard.
 */

export type ApiConnectionState =
  | "unknown"
  | "reachable"
  | "degraded"
  | "unreachable";

type Listener = (state: ApiConnectionState) => void;

let state: ApiConnectionState = "unknown";
const listeners = new Set<Listener>();

/** Soft failures (timeouts / abort). */
let softFailures = 0;
/** Hard failures (failed to fetch / DNS / CORS / offline). */
let hardFailures = 0;

const SOFT_DEGRADED_AT = 2;
const SOFT_UNREACHABLE_AT = 8;
const HARD_UNREACHABLE_AT = 2;

function emit(next: ApiConnectionState) {
  if (state === next) return;
  state = next;
  for (const l of listeners) l(state);
}

function recompute() {
  if (hardFailures >= HARD_UNREACHABLE_AT || softFailures >= SOFT_UNREACHABLE_AT) {
    emit("unreachable");
    return;
  }
  if (softFailures >= SOFT_DEGRADED_AT || hardFailures >= 1) {
    emit("degraded");
    return;
  }
  if (state === "unknown") return;
  emit("reachable");
}

export function getApiConnectionState(): ApiConnectionState {
  return state;
}

export function subscribeApiConnection(fn: Listener): () => void {
  listeners.add(fn);
  fn(state);
  return () => {
    listeners.delete(fn);
  };
}

/** Any successful HTTP response from the API. */
export function markApiReachable() {
  softFailures = 0;
  hardFailures = 0;
  emit("reachable");
}

/**
 * @deprecated Prefer noteApiTimeout / noteApiNetworkFailure.
 * Kept for compatibility; treated as a soft failure.
 */
export function markApiUnreachable() {
  noteApiTimeout();
}

/** Client AbortSignal timeout — API may still be alive under load. */
export function noteApiTimeout() {
  softFailures += 1;
  recompute();
}

/**
 * Health-probe timeout under ITE load — cap at degraded.
 * Never escalate probe-only timeouts to unreachable.
 */
export function noteApiSlow() {
  softFailures = Math.min(Math.max(softFailures, SOFT_DEGRADED_AT), SOFT_DEGRADED_AT);
  recompute();
}

/** Browser/network failure — failed to fetch, DNS, CORS, offline. */
export function noteApiNetworkFailure() {
  hardFailures += 1;
  softFailures += 1;
  recompute();
}

export function isNetworkFailure(error: unknown): boolean {
  if (!error) return false;
  if (error instanceof TypeError) return true;
  if (error instanceof Error) {
    const m = error.message.toLowerCase();
    return (
      m.includes("failed to fetch") ||
      m.includes("networkerror") ||
      m.includes("load failed") ||
      m.includes("network request failed") ||
      m === "network_error"
    );
  }
  return false;
}
