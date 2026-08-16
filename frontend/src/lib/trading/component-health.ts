/**
 * Authoritative LIVE component health for Mission Control / ops surfaces.
 *
 * Source of truth: GET /api/v1/health/trading-components (no auth).
 * Session / weltrade / mt5-status feeds are secondary and must not flip a
 * recently confirmed HEALTHY/CONNECTED plane to Disconnected on a single
 * timeout or process-local session miss.
 */

import { asRecord, str } from "@/lib/desk";

export type ComponentPlane = "gateway" | "mt5" | "oms" | "ai";

export type PlaneHealth = {
  /** true = up, false = down, null = unknown / checking */
  ok: boolean | null;
  status: string;
  detail: string;
  latencyMs: number | null;
  /** True when value comes from last-known-good hysteresis. */
  stale: boolean;
};

export type TradingComponentsView = {
  gateway: PlaneHealth;
  mt5: PlaneHealth;
  oms: PlaneHealth;
  ai: PlaneHealth;
  rawStatuses: Record<string, string>;
  updatedAt: number;
};

const LAST_GOOD_TTL_MS = 5 * 60_000;

type LastGood = {
  view: TradingComponentsView;
  at: number;
};

let lastGood: LastGood | null = null;

function plane(
  ok: boolean | null,
  status: string,
  detail = "",
  latencyMs: number | null = null,
  stale = false,
): PlaneHealth {
  return { ok, status, detail, latencyMs, stale };
}

function parseGateway(status: string, evidence: Record<string, unknown>, detail: string): PlaneHealth {
  const u = status.toUpperCase();
  const latency = Number(evidence.latency_ms);
  const latencyMs = Number.isFinite(latency) ? latency : null;
  if (u === "HEALTHY" || u === "UP" || u === "OK") {
    return plane(true, u || "HEALTHY", detail, latencyMs);
  }
  if (u === "DOWN" || u === "UNHEALTHY" || u === "UNREACHABLE" || u === "DISCONNECTED") {
    return plane(false, u, detail, latencyMs);
  }
  return plane(null, u || "UNKNOWN", detail, latencyMs);
}

function parseMt5(status: string, evidence: Record<string, unknown>, detail: string): PlaneHealth {
  const u = status.toUpperCase();
  if (u === "CONNECTED" || u === "HEALTHY" || u === "OK") {
    return plane(true, u || "CONNECTED", detail);
  }
  if (u === "DISCONNECTED" || u === "DOWN" || u === "UNHEALTHY") {
    return plane(false, u, detail);
  }
  // Fall back to evidence.connected when status string is missing.
  if (evidence.connected === true) return plane(true, "CONNECTED", detail);
  if (evidence.connected === false) return plane(false, "DISCONNECTED", detail);
  return plane(null, u || "UNKNOWN", detail);
}

function parseGeneric(status: string, detail: string): PlaneHealth {
  const u = status.toUpperCase();
  if (u === "HEALTHY" || u === "OK" || u === "READY" || u === "CONNECTED") {
    return plane(true, u, detail);
  }
  if (u === "DOWN" || u === "UNHEALTHY" || u === "NOT_READY" || u === "DISABLED") {
    return plane(false, u, detail);
  }
  return plane(null, u || "UNKNOWN", detail);
}

/** Parse a trading-components JSON body into plane health. */
export function parseTradingComponentsPayload(
  payload: unknown,
  now = Date.now(),
): TradingComponentsView | null {
  const root = asRecord(payload);
  if (!Object.keys(root).length) return null;
  const statuses = asRecord(root.statuses);
  const gateway = asRecord(root.gateway);
  const mt5 = asRecord(root.mt5);
  const oms = asRecord(root.oms);
  const ai = asRecord(root.ai);

  const gwStatus = str(statuses.gateway || gateway.status, "").toUpperCase();
  const mt5Status = str(statuses.mt5 || mt5.status, "").toUpperCase();
  const omsStatus = str(statuses.oms || oms.status, "").toUpperCase();
  const aiStatus = str(statuses.ai || ai.status, "").toUpperCase();

  const view: TradingComponentsView = {
    gateway: parseGateway(
      gwStatus,
      asRecord(gateway.evidence),
      str(gateway.detail, ""),
    ),
    mt5: parseMt5(mt5Status, asRecord(mt5.evidence), str(mt5.detail, "")),
    oms: parseGeneric(omsStatus, str(oms.detail, "")),
    ai: parseGeneric(aiStatus, str(ai.detail, "")),
    rawStatuses: {
      gateway: gwStatus,
      mt5: mt5Status,
      oms: omsStatus,
      ai: aiStatus,
    },
    updatedAt: now,
  };

  // Only cache definitive good/bad planes — not empty unknown payloads.
  if (view.gateway.ok != null || view.mt5.ok != null) {
    lastGood = { view, at: now };
  }
  return view;
}

/**
 * Resolve plane health with hysteresis:
 * - Prefer fresh trading-components parse
 * - On miss/timeout, reuse last-known-good within TTL (marked stale)
 * - Never invent Connected without evidence
 */
export function resolveTradingComponentsView(args: {
  payload?: unknown;
  isSuccess?: boolean;
  isError?: boolean;
  errorKind?: "timeout" | "network" | "other" | null;
  now?: number;
}): TradingComponentsView | null {
  const now = args.now ?? Date.now();
  if (args.isSuccess && args.payload != null) {
    return parseTradingComponentsPayload(args.payload, now);
  }

  if (
    lastGood &&
    now - lastGood.at <= LAST_GOOD_TTL_MS &&
    (args.isError || args.errorKind === "timeout" || args.errorKind === "network")
  ) {
    const staleView: TradingComponentsView = {
      ...lastGood.view,
      gateway: { ...lastGood.view.gateway, stale: true },
      mt5: { ...lastGood.view.mt5, stale: true },
      oms: { ...lastGood.view.oms, stale: true },
      ai: { ...lastGood.view.ai, stale: true },
      updatedAt: lastGood.at,
    };
    return staleView;
  }

  return null;
}

/** Merge secondary session/broker signals without overriding authoritative health. */
export function mergePlaneOk(
  authoritative: boolean | null,
  secondary: boolean | null | undefined,
): boolean | null {
  if (authoritative === true) return true;
  if (authoritative === false) return false;
  if (secondary == null) return null;
  return Boolean(secondary);
}

/** Display label for Mission Control / recovery rows. */
export function planeConnectionLabel(ok: boolean | null, stale = false): string {
  if (ok === true) return stale ? "Connected (cached)" : "Connected";
  if (ok === false) return "Disconnected";
  return "Unknown";
}

/** Normalize control-center strings (up/down/connected) for executive overlay. */
export function overlayExecutiveStatus(
  controlCenterValue: unknown,
  plane: PlaneHealth | null | undefined,
): string {
  if (plane?.ok === true) return "Connected";
  if (plane?.ok === false) return "Disconnected";
  const raw = str(controlCenterValue, "").trim();
  if (!raw) return "—";
  const u = raw.toLowerCase();
  if (u === "up" || u === "healthy" || u === "connected" || u === "ok") {
    return "Connected";
  }
  if (u === "down" || u === "disconnected" || u === "unhealthy") {
    return "Disconnected";
  }
  return raw;
}

/** Test helper — clear hysteresis cache. */
export function resetTradingComponentsLastGood(): void {
  lastGood = null;
}
