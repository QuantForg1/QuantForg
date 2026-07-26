/**
 * Frontend ↔ API reachability (presentation signal only).
 * Updated by apiFetch; consumed by ConnectionBanner.
 */

export type ApiConnectionState = "unknown" | "reachable" | "unreachable";

type Listener = (state: ApiConnectionState) => void;

let state: ApiConnectionState = "unknown";
const listeners = new Set<Listener>();

function emit(next: ApiConnectionState) {
  if (state === next) return;
  state = next;
  for (const l of listeners) l(state);
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

export function markApiReachable() {
  emit("reachable");
}

export function markApiUnreachable() {
  emit("unreachable");
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
