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

/** Typewriter step: how many characters to reveal this frame. */
export function revealStep(remaining: number): number {
  if (remaining <= 0) return 0;
  return Math.min(remaining, Math.max(2, Math.ceil(remaining / 24)));
}
