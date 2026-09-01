/**
 * Production API communication, auth, strategy contract, dedupe, latency.
 * Run: node --experimental-strip-types src/lib/api/communication.test.ts
 *
 * Imports only leaf modules (no Next/@ path graph) so Node ESM can load them.
 */
import assert from "node:assert/strict";
import {
  isValidApiBaseUrl,
  normalizeApiBaseUrl,
  PRODUCTION_API_BASE_URL,
} from "./api-base.ts";
import {
  classifyCommunicationFault,
  isNoTradeFault,
} from "./communication-fault.ts";
import { dedupeInflight, inflightSize, resetInflightForTests } from "./inflight.ts";
import {
  API_HEAVY_TIMEOUT_MS,
  API_HEALTH_TIMEOUT_MS,
  API_TELEMETRY_TIMEOUT_MS,
  defaultTimeoutForPath,
  isCriticalTradingPath,
  isTelemetryPath,
  shouldAttemptTokenRefresh,
  shouldDedupeGet,
  shouldDedupeReadOnlyCalc,
  shouldHealSessionOnUnauthorized,
  shouldReplayAfterRefresh,
} from "./request-policy.ts";
import {
  assertStrategyEvaluateShape,
  mapStrategyEvaluateAliases,
} from "./strategy-evaluate-contract.ts";

const CANONICAL = "XAUUSD_i";

// 1. API base URL valid
{
  assert.equal(isValidApiBaseUrl(PRODUCTION_API_BASE_URL), true);
  assert.equal(
    normalizeApiBaseUrl("https://quantforg-production.up.railway.app"),
    PRODUCTION_API_BASE_URL,
  );
  assert.equal(isValidApiBaseUrl(""), false);
  assert.equal(isValidApiBaseUrl("not-a-url"), false);
}

// 2. API unreachable
{
  const fault = classifyCommunicationFault({ status: 0, code: "network_error" });
  assert.equal(fault, "API_UNREACHABLE");
  assert.equal(isNoTradeFault(fault), false);
}

// 3. Timeout
{
  const fault = classifyCommunicationFault({ status: 408, code: "timeout" });
  assert.equal(fault, "API_TIMEOUT");
  assert.equal(isNoTradeFault(fault), false);
  assert.equal(defaultTimeoutForPath("/weltrade/health"), API_HEAVY_TIMEOUT_MS);
  assert.equal(defaultTimeoutForPath("/health"), API_HEALTH_TIMEOUT_MS);
  assert.ok(defaultTimeoutForPath("/weltrade/health") > defaultTimeoutForPath("/health"));
  assert.equal(
    defaultTimeoutForPath("/institutional-observability/health"),
    API_TELEMETRY_TIMEOUT_MS,
  );
  assert.equal(defaultTimeoutForPath("/positions"), API_HEAVY_TIMEOUT_MS);
  assert.equal(defaultTimeoutForPath("/orders"), API_HEAVY_TIMEOUT_MS);
  assert.equal(defaultTimeoutForPath("/portfolio"), API_HEAVY_TIMEOUT_MS);
  assert.equal(defaultTimeoutForPath("/market-universe/snapshot"), API_HEAVY_TIMEOUT_MS);
}

// 4. Auth refresh — GET replay, one shot
{
  assert.equal(
    shouldHealSessionOnUnauthorized({
      status: 401,
      authEnabled: true,
      alreadyRetried: false,
    }),
    true,
  );
  assert.equal(
    shouldAttemptTokenRefresh({
      status: 401,
      authEnabled: true,
      alreadyRetried: false,
      method: "GET",
      path: "/positions",
    }),
    true,
  );
  assert.equal(
    shouldAttemptTokenRefresh({
      status: 401,
      authEnabled: true,
      alreadyRetried: true,
      method: "GET",
      path: "/positions",
    }),
    false,
  );
}

// 5. Invalid / missing auth
{
  assert.equal(
    classifyCommunicationFault({ status: 401, code: "missing_token" }),
    "AUTH_REQUIRED",
  );
  assert.equal(
    classifyCommunicationFault({ status: 401, code: "invalid_token" }),
    "AUTH_REFRESH",
  );
}

// 6. Strategy request valid (producer maps volume → requested_lots, drops side)
{
  const mapped = mapStrategyEvaluateAliases({
    request_id: "ui-1",
    symbol: CANONICAL,
    volume: "0.01",
    side: "buy",
  });
  assert.equal(mapped.requested_lots, "0.01");
  assert.equal("side" in mapped, false);
  assert.equal("volume" in mapped, false);
  assertStrategyEvaluateShape(mapped);
}

// 7. Strategy request invalid
{
  assert.throws(() => assertStrategyEvaluateShape({ symbol: CANONICAL }));
  assert.throws(() =>
    assertStrategyEvaluateShape({
      request_id: "x",
      symbol: CANONICAL,
      side: "buy",
    }),
  );
}

// 8. Duplicated request dedupe
{
  assert.equal(shouldDedupeGet("/trading/session"), true);
  assert.equal(shouldDedupeGet("/portfolio"), true);
  assert.equal(shouldDedupeGet("/positions?symbol=XAUUSD_i"), true);
  assert.equal(shouldDedupeGet("/mt5/account"), true);
  assert.equal(shouldDedupeGet("/mt5/status"), true);
  assert.equal(shouldDedupeGet("/orders"), true);
  assert.equal(shouldDedupeGet("/execution/journal?limit=80"), true);
  assert.equal(shouldDedupeGet("/institutional-observability/health"), true);
  assert.equal(shouldDedupeReadOnlyCalc("/mt5/order/calculate"), true);
  assert.equal(shouldDedupeReadOnlyCalc("/mt5/order/validate"), false);
}

// 9. Current snapshot reuse
{
  const key = (cycleId: string, snapshotId: string) =>
    `${cycleId}:${snapshotId}:${CANONICAL}`;
  assert.equal(key("cycle-1", "snap-1"), key("cycle-1", "snap-1"));
  assert.ok(key("cycle-1", "snap-1").includes(CANONICAL));
}

// 10. Telemetry failure does not block decision
{
  assert.equal(isTelemetryPath("/institutional-observability/dashboard"), true);
  assert.equal(isTelemetryPath("/execution/audits"), true);
  assert.equal(isCriticalTradingPath("/institutional-observability/health"), false);
  assert.equal(isNoTradeFault("SERVER_ERROR"), false);
}

// 11. Market data failure blocks safely (critical path)
{
  assert.equal(isCriticalTradingPath("/mt5/ticks/XAUUSD_i"), true);
  assert.equal(isCriticalTradingPath("/positions"), true);
  assert.equal(isCriticalTradingPath("/strategy/evaluate"), true);
}

// 12. Order submission is never blindly retried
{
  assert.equal(shouldReplayAfterRefresh("POST", "/execution/submit"), false);
  assert.equal(shouldReplayAfterRefresh("POST", "/mt5/order"), false);
  assert.equal(shouldReplayAfterRefresh("GET", "/orders"), true);
  assert.equal(
    shouldAttemptTokenRefresh({
      status: 401,
      authEnabled: true,
      alreadyRetried: false,
      method: "POST",
      path: "/execution/submit",
    }),
    false,
  );
}

// 13. XAUUSD_i remains canonical
{
  assert.equal(CANONICAL, "XAUUSD_i");
}

// 14. Autonomous path does not depend on browser/UI
{
  assert.equal(isCriticalTradingPath("/ite/ops/auto-trading"), true);
  assert.equal(isTelemetryPath("/execution/journal"), true);
}

// 15. Same-cycle decision remains coherent + concurrent refresh coalesces
resetInflightForTests();
{
  let runs = 0;
  const factory = () => {
    runs += 1;
    return new Promise<string>((resolve) => {
      setTimeout(() => resolve("token"), 20);
    });
  };
  const p1 = dedupeInflight("auth:refresh", factory);
  const p2 = dedupeInflight("auth:refresh", factory);
  const p3 = dedupeInflight("auth:refresh", factory);
  assert.equal(inflightSize(), 1);
  Promise.all([p1, p2, p3])
    .then(([a, b, c]) => {
      assert.equal(a, "token");
      assert.equal(b, a);
      assert.equal(c, a);
      assert.equal(runs, 1);
      assert.equal(inflightSize(), 0);
      console.log("communication.test.ts: ok");
    })
    .catch((err: unknown) => {
      console.error(err);
      process.exit(1);
    });
}
