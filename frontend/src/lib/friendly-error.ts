/**
 * Turn engineering-style load errors into calm, customer-facing text.
 * "Strategy Lab could not be loaded." -> "Reconnecting to Strategy Lab…"
 */
export function friendlyLoadMessage(message: string): string {
  const text = (message || "").trim();
  const m = /^(.+?)\s+(?:could not|couldn't|failed to)\s+(?:be\s+)?(?:load|loaded|fetch|fetched|read)\b/i.exec(text);
  if (m) return `Reconnecting to ${m[1].replace(/^the\s+/i, "")}…`;
  if (/^unable to load/i.test(text) || /^failed to load/i.test(text)) return "Reconnecting…";
  return text;
}
