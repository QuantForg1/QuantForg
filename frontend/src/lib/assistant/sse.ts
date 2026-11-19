/** Parse one SSE frame ("event: x\ndata: {...}"). */
export function parseSseFrame(frame: string): { event: string; data: Record<string, unknown> } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) as Record<string, unknown> };
  } catch {
    return null;
  }
}

/** Absolute API origin first (no proxy buffering), then the runtime base. */
export function streamBaseCandidates(configured: string, runtime: string): string[] {
  const clean = (v: string) => v.replace(/\/+$/, "");
  const out: string[] = [];
  if (/^https?:\/\//.test(configured)) out.push(clean(configured));
  if (runtime && !out.includes(clean(runtime))) out.push(clean(runtime));
  return out;
}
