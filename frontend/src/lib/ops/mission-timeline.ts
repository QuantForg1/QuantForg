import { asList, asRecord, str } from "@/lib/desk";

export type TimelineEvent = {
  id: string;
  at: string;
  title: string;
  detail: string;
  href?: string;
  tone: "ok" | "warn" | "off" | "neutral";
};

function pickTime(row: Record<string, unknown>): string {
  return str(
    row.at ||
      row.timestamp ||
      row.created_at ||
      row.ts ||
      row.time ||
      row.as_of ||
      "",
  );
}

export function rowsFromFeed(payload: unknown): Record<string, unknown>[] {
  const rec = asRecord(payload);
  return asList(
    rec.items ||
      rec.entries ||
      rec.events ||
      rec.audit ||
      rec.journal ||
      payload,
  ).map(asRecord);
}

export function classifyTimelineRow(row: Record<string, unknown>): TimelineEvent {
  const title = str(
    row.event ||
      row.action ||
      row.type ||
      row.stage ||
      row.message ||
      row.outcome ||
      "Event",
  );
  const detail = str(
    row.detail ||
      row.reason ||
      row.symbol ||
      row.request_id ||
      row.status ||
      "",
  );
  const lower = `${title} ${detail}`.toLowerCase();
  let tone: TimelineEvent["tone"] = "neutral";
  if (/accept|connected|approved|recovered|filled|closed|success|ok/.test(lower)) {
    tone = "ok";
  } else if (/reject|fail|error|timeout|disconnect|kill/.test(lower)) {
    tone = "off";
  } else if (/retry|degraded|warn|pending|risk|scan/.test(lower)) {
    tone = "warn";
  }
  const id = str(row.id || row.request_id || `${pickTime(row)}:${title}`);
  return {
    id,
    at: pickTime(row) || new Date().toISOString(),
    title,
    detail,
    href: row.request_id
      ? `/execution/diagnostics?request_id=${encodeURIComponent(String(row.request_id))}`
      : undefined,
    tone,
  };
}

export function mergeTimelineEvents(
  journalPayload: unknown,
  auditPayload: unknown,
  limit = 80,
): TimelineEvent[] {
  return [...rowsFromFeed(journalPayload), ...rowsFromFeed(auditPayload)]
    .map(classifyTimelineRow)
    .filter((e) => e.title && e.title !== "Event")
    .sort((a, b) => Date.parse(b.at) - Date.parse(a.at))
    .slice(0, limit);
}
