/**
 * Status derivations for operator desks.
 *
 * EXECUTION_ENABLED (deployment) and the MT5 adapter order-send gate are
 * different facts. A missing health field is unknown, never "disabled".
 * The Railway dot means this API process answered, not that every dependency
 * is healthy.
 */

export type ExecutionLabel = "enabled" | "disabled" | "unknown";

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

const UP = /^(ok|up|healthy|pass|serving|online)$/i;
const DOWN = /^(down|offline|unreachable|unhealthy|error|failed)$/i;

export function adapterExecutionEnabled(payload: unknown): boolean | null {
  const rec = asRecord(payload);
  if (typeof rec.execution_enabled === "boolean") return rec.execution_enabled;
  const nested = asRecord(rec.configuration).execution_enabled;
  if (typeof nested === "boolean") return nested;
  return null;
}

export function adapterExecutionLabel(payload: unknown): ExecutionLabel {
  const flag = adapterExecutionEnabled(payload);
  if (flag === true) return "enabled";
  if (flag === false) return "disabled";
  return "unknown";
}

export type RailwayProbeInput = {
  servicesHealth: unknown;
  servicesHealthSuccess: boolean;
  servicesHealthError: boolean;
  observability: unknown;
  apiHealth: unknown;
  apiHealthError: boolean;
  apiHealthSuccess: boolean;
};

function upOrDown(value: unknown): boolean | null {
  if (value == null || value === "") return null;
  const text = String(value).trim();
  if (UP.test(text)) return true;
  if (DOWN.test(text)) return false;
  return null;
}

function apiServiceRow(servicesHealth: unknown): Record<string, unknown> | null {
  const services = asRecord(servicesHealth).services;
  if (!Array.isArray(services)) return null;
  for (const row of services) {
    const record = asRecord(row);
    if (String(record.name || "").toLowerCase() === "api") return record;
  }
  return null;
}

/**
 * Railway process reachability.
 * Prefer the services-health `api` row: that handler runs inside Railway.
 * Degraded or halted component rows are not a Railway outage.
 */
export function railwayProcessOk(input: RailwayProbeInput): boolean | null {
  const apiRow = apiServiceRow(input.servicesHealth);
  if (apiRow) {
    const fromRow = upOrDown(apiRow.status);
    if (fromRow !== null) return fromRow;
  }
  if (input.servicesHealthSuccess && input.servicesHealth != null) return true;

  const explicit = upOrDown(asRecord(asRecord(input.servicesHealth).railway).status);
  if (explicit !== null) return explicit;

  const obs = asRecord(input.observability);
  const components = asRecord(obs.components ?? obs);
  const fromObs = upOrDown(asRecord(components.api).status);
  if (fromObs !== null) return fromObs;

  if (input.apiHealthError) {
    return input.servicesHealthError ? false : null;
  }
  const fromApi = upOrDown(asRecord(input.apiHealth).status);
  if (fromApi !== null) return fromApi;
  if (input.apiHealthSuccess) return true;
  return null;
}
