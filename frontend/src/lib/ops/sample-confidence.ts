/** Sample-size labels for Strategy Research. Analytical only. */

export const INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE";
export const EARLY_SIGNAL = "EARLY_SIGNAL";
export const PRELIMINARY = "PRELIMINARY";
export const MEANINGFUL_RESEARCH = "MEANINGFUL_RESEARCH";
export const STRONGER_EVIDENCE = "STRONGER_EVIDENCE";
export const HIGHER_CONFIDENCE = "HIGHER_CONFIDENCE";
/** Alias of MEANINGFUL_RESEARCH (research label only). */
export const MEANINGFUL = MEANINGFUL_RESEARCH;

export function sampleStatus(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return INSUFFICIENT_SAMPLE;
  if (n < 10) return EARLY_SIGNAL;
  if (n < 20) return PRELIMINARY;
  if (n < 50) return MEANINGFUL_RESEARCH;
  if (n < 100) return STRONGER_EVIDENCE;
  return HIGHER_CONFIDENCE;
}

export function displayMetric(
  value: unknown,
  status: string,
  fallback = "INSUFFICIENT SAMPLE",
): string {
  if (status === INSUFFICIENT_SAMPLE) return fallback;
  if (value == null || value === "" || value === "UNKNOWN") return fallback;
  return String(value);
}

/** Always pair a rate with its sample size. n<10 never prints a fake 80–90%. */
export function formatRate(rate: unknown, n: number, status?: string): string {
  const label = status || sampleStatus(n);
  if (n < 10 || label === INSUFFICIENT_SAMPLE || rate == null || rate === "UNKNOWN") {
    return `INSUFFICIENT SAMPLE n=${n}`;
  }
  const text = String(rate);
  return text.includes("n=") ? text : `${text}% n=${n}`;
}
