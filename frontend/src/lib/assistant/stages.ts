import type { AssistantStage } from "./stream";

/** Merge a stage update into the list (same key replaces, keeps order). */
export function upsertStage(list: AssistantStage[], next: AssistantStage): AssistantStage[] {
  const i = list.findIndex((s) => s.key === next.key);
  if (i === -1) return [...list, next];
  const copy = list.slice();
  copy[i] = { ...copy[i], ...next };
  return copy;
}

/** Mark every still-active stage done (answer finished or stopped). */
export function settleStages(list: AssistantStage[]): AssistantStage[] {
  return list.map((s) => (s.status === "active" ? { ...s, status: "done" as const } : s));
}

/**
 * Typewriter pace in characters per second: steady and readable, slightly
 * faster when far behind so very long answers never lag by more than a few
 * seconds. ~1,000 characters type out in about 7 seconds.
 */
export function revealRate(remaining: number): number {
  if (remaining <= 0) return 0;
  return Math.min(180, 70 + remaining * 0.12);
}

/**
 * Advance the visible length by whole words that fit in `chars` (the time
 * budget). A word longer than 16 characters may be split so it never stalls.
 */
export function revealTo(text: string, shown: number, chars: number): number {
  if (shown >= text.length) return text.length;
  let next = shown;
  for (;;) {
    let end = next;
    while (end < text.length && /\s/.test(text[end])) end += 1;
    while (end < text.length && !/\s/.test(text[end])) end += 1;
    if (end === next) break;
    if (end - shown <= chars) {
      next = end;
      continue;
    }
    if (next === shown && end - shown > 16 && chars >= 1) {
      next = shown + Math.floor(chars);
    }
    break;
  }
  return Math.min(next, text.length);
}

/** Legacy frame step (kept for callers/tests). */
export function revealStep(remaining: number): number {
  if (remaining <= 0) return 0;
  return Math.min(remaining, Math.max(2, Math.ceil(remaining / 24)));
}
