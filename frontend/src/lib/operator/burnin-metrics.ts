/**
 * RC2 Live Burn-in metrics — client-side historical ring buffer.
 * Derived from observed LIVE API samples only. Never mutates Trading Core.
 */

export type BurnInSample = {
  at: string;
  tradesDay: number;
  tradesHour: number;
  winRate: number | null;
  profitFactor: number | null;
  avgRr: number | null;
  avgHoldMs: number | null;
  eligibleSymbols: number | null;
  ordersSubmitted: number | null;
  ordersAccepted: number | null;
  ordersRejected: number | null;
  gatewayReconnects: number;
  brokerReconnects: number;
  apiLatencyMs: number | null;
  dashboardLatencyMs: number | null;
  scannerLatencyMs: number | null;
  omsLatencyMs: number | null;
  pmeLatencyMs: number | null;
  memoryMb: number | null;
  cpuPct: number | null;
  gatewayOnline: boolean | null;
  brokerOnline: boolean | null;
};

const KEY = "qf.rc2.burnin.metrics.v1";
const RECONNECT_KEY = "qf.rc2.burnin.reconnects.v1";
const MAX = 288; // ~24h at 5min if sampled frequently; capped

type ReconnectCounters = {
  gateway: number;
  broker: number;
  lastGateway?: boolean | null;
  lastBroker?: boolean | null;
};

function loadReconnects(): ReconnectCounters {
  try {
    const raw = localStorage.getItem(RECONNECT_KEY);
    if (raw) return JSON.parse(raw) as ReconnectCounters;
  } catch {
    /* ignore */
  }
  return { gateway: 0, broker: 0, lastGateway: null, lastBroker: null };
}

function saveReconnects(c: ReconnectCounters) {
  try {
    localStorage.setItem(RECONNECT_KEY, JSON.stringify(c));
  } catch {
    /* ignore */
  }
}

/** Track edge transitions as reconnects (observed UI health only). */
export function noteConnectivitySample(
  gatewayOnline: boolean | null,
  brokerOnline: boolean | null,
): ReconnectCounters {
  const cur = loadReconnects();
  if (cur.lastGateway === true && gatewayOnline === false) {
    /* disconnect counted on recovery */
  }
  if (cur.lastGateway === false && gatewayOnline === true) {
    cur.gateway += 1;
  }
  if (cur.lastBroker === false && brokerOnline === true) {
    cur.broker += 1;
  }
  cur.lastGateway = gatewayOnline;
  cur.lastBroker = brokerOnline;
  saveReconnects(cur);
  return cur;
}

export function listBurnInSamples(): BurnInSample[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as BurnInSample[]) : [];
  } catch {
    return [];
  }
}

export function recordBurnInSample(
  sample: Omit<BurnInSample, "at" | "gatewayReconnects" | "brokerReconnects"> & {
    at?: string;
    gatewayOnline?: boolean | null;
    brokerOnline?: boolean | null;
  },
): BurnInSample {
  const recon = noteConnectivitySample(
    sample.gatewayOnline ?? null,
    sample.brokerOnline ?? null,
  );
  const finite = (v: number | null | undefined): number | null =>
    v == null || !Number.isFinite(v) ? null : v;
  const row: BurnInSample = {
    at: sample.at || new Date().toISOString(),
    tradesDay: sample.tradesDay,
    tradesHour: sample.tradesHour,
    winRate: finite(sample.winRate),
    profitFactor: finite(sample.profitFactor),
    avgRr: finite(sample.avgRr),
    avgHoldMs: finite(sample.avgHoldMs),
    eligibleSymbols: finite(sample.eligibleSymbols),
    ordersSubmitted: finite(sample.ordersSubmitted),
    ordersAccepted: finite(sample.ordersAccepted),
    ordersRejected: finite(sample.ordersRejected),
    gatewayReconnects: recon.gateway,
    brokerReconnects: recon.broker,
    apiLatencyMs: finite(sample.apiLatencyMs),
    dashboardLatencyMs: finite(sample.dashboardLatencyMs),
    scannerLatencyMs: finite(sample.scannerLatencyMs),
    omsLatencyMs: finite(sample.omsLatencyMs),
    pmeLatencyMs: finite(sample.pmeLatencyMs),
    memoryMb: finite(sample.memoryMb),
    cpuPct: finite(sample.cpuPct),
    gatewayOnline: sample.gatewayOnline ?? null,
    brokerOnline: sample.brokerOnline ?? null,
  };
  const next = [row, ...listBurnInSamples()].slice(0, MAX);
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* ignore */
  }
  return row;
}

export function latestBurnInSample(): BurnInSample | null {
  return listBurnInSamples()[0] ?? null;
}

export function burnInSamplesCsv(rows: BurnInSample[]): string {
  const headers = [
    "at",
    "trades_day",
    "trades_hour",
    "win_rate",
    "profit_factor",
    "avg_rr",
    "avg_hold_ms",
    "eligible_symbols",
    "orders_submitted",
    "orders_accepted",
    "orders_rejected",
    "gateway_reconnects",
    "broker_reconnects",
    "api_latency_ms",
    "dashboard_latency_ms",
    "scanner_latency_ms",
    "oms_latency_ms",
    "pme_latency_ms",
    "memory_mb",
    "cpu_pct",
  ];
  const esc = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /["\n,]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [
    headers.join(","),
    ...rows.map((r) =>
      [
        r.at,
        r.tradesDay,
        r.tradesHour,
        r.winRate,
        r.profitFactor,
        r.avgRr,
        r.avgHoldMs,
        r.eligibleSymbols,
        r.ordersSubmitted,
        r.ordersAccepted,
        r.ordersRejected,
        r.gatewayReconnects,
        r.brokerReconnects,
        r.apiLatencyMs,
        r.dashboardLatencyMs,
        r.scannerLatencyMs,
        r.omsLatencyMs,
        r.pmeLatencyMs,
        r.memoryMb,
        r.cpuPct,
      ]
        .map(esc)
        .join(","),
    ),
  ].join("\n");
}
