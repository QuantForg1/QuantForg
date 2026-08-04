/**
 * Client-side API request telemetry for the API Inspector.
 * Presentation only — never invents server metrics.
 */

export type ApiRequestSample = {
  id: string;
  at: string;
  method: string;
  path: string;
  status: number;
  latencyMs: number;
  sizeBytes: number | null;
  retries: number;
  timedOut: boolean;
  error?: string;
  requestId?: string;
};

const MAX = 200;
const listeners = new Set<(rows: ApiRequestSample[]) => void>();
let buffer: ApiRequestSample[] = [];

function emit() {
  const snapshot = buffer.slice(0, MAX);
  for (const l of listeners) l(snapshot);
}

export function listApiRequestSamples(): ApiRequestSample[] {
  return buffer.slice(0, MAX);
}

export function clearApiRequestSamples() {
  buffer = [];
  emit();
}

export function subscribeApiRequestSamples(
  fn: (rows: ApiRequestSample[]) => void,
): () => void {
  listeners.add(fn);
  fn(listApiRequestSamples());
  return () => {
    listeners.delete(fn);
  };
}

export function recordApiRequestSample(
  sample: Omit<ApiRequestSample, "id" | "at"> & { id?: string; at?: string },
) {
  const row: ApiRequestSample = {
    id: sample.id || `req_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`,
    at: sample.at || new Date().toISOString(),
    method: sample.method,
    path: sample.path,
    status: sample.status,
    latencyMs: sample.latencyMs,
    sizeBytes: sample.sizeBytes,
    retries: sample.retries,
    timedOut: sample.timedOut,
    error: sample.error,
    requestId: sample.requestId,
  };
  buffer = [row, ...buffer].slice(0, MAX);
  emit();
}

export function exportApiRequestSamplesCsv(rows: ApiRequestSample[]): string {
  const header = [
    "at",
    "method",
    "path",
    "status",
    "latency_ms",
    "size_bytes",
    "retries",
    "timed_out",
    "error",
    "request_id",
  ];
  const lines = rows.map((r) =>
    [
      r.at,
      r.method,
      r.path,
      r.status,
      r.latencyMs,
      r.sizeBytes ?? "",
      r.retries,
      r.timedOut,
      JSON.stringify(r.error ?? ""),
      r.requestId ?? "",
    ].join(","),
  );
  return [header.join(","), ...lines].join("\n");
}
