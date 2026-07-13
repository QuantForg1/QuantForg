/** Exponential backoff with jitter for failed channel polls. */

export function createBackoff(opts?: {
  baseMs?: number;
  maxMs?: number;
  factor?: number;
}) {
  const baseMs = opts?.baseMs ?? 1_000;
  const maxMs = opts?.maxMs ?? 60_000;
  const factor = opts?.factor ?? 2;
  let attempt = 0;

  return {
    reset() {
      attempt = 0;
    },
    next(): number {
      const exp = Math.min(maxMs, baseMs * factor ** attempt);
      attempt += 1;
      const jitter = exp * (0.2 * Math.random());
      return Math.round(exp + jitter);
    },
    get attempts() {
      return attempt;
    },
  };
}
