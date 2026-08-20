/**
 * In-flight promise coalescing — one key, one network call.
 * Used for GET dedupe and single-flight token refresh.
 */

const inflight = new Map<string, Promise<unknown>>();

export function dedupeInflight<T>(key: string, factory: () => Promise<T>): Promise<T> {
  const existing = inflight.get(key);
  if (existing) return existing as Promise<T>;
  const pending = factory().finally(() => {
    inflight.delete(key);
  });
  inflight.set(key, pending);
  return pending;
}

export function inflightSize(): number {
  return inflight.size;
}

export function resetInflightForTests(): void {
  inflight.clear();
}
