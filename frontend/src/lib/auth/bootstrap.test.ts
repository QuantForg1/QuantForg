/**
 * Auth bootstrap + Auto Trading surface regression.
 * Run: node --experimental-strip-types src/lib/auth/bootstrap.test.ts
 */
import assert from "node:assert/strict";
import {
  canIssueProtectedOps,
  isAuthenticatedPhase,
  resolveAuthPhase,
} from "./bootstrap";
import {
  API_AUTH_TIMEOUT_MS,
  API_HEALTH_LIVE_TIMEOUT_MS,
  API_HEALTH_TIMEOUT_MS,
  defaultTimeoutForPath,
  sessionBootBudgetMs,
  shouldAttemptTokenRefresh,
  shouldDedupeGet,
} from "../api/request-policy";
import {
  autoTradingSurfaceCopy,
  classifyOpsFailure,
  OPS_SLOW_MS,
  resolveAutoTradingSurface,
  resolveApiPhase,
  resolveTradingInfraState,
} from "../ops/auto-trading-surface";
import {
  readOpsTelemetry,
  rememberOpsTelemetry,
  resetOpsTelemetryLastGood,
} from "../ops/ops-telemetry-cache";

function surface(partial: {
  authPhase?: Parameters<typeof resolveAutoTradingSurface>[0]["authPhase"];
  opsQuery?: Parameters<typeof resolveAutoTradingSurface>[0]["opsQuery"];
  hasOpsData?: boolean;
  tradingInfra?: Parameters<typeof resolveAutoTradingSurface>[0]["tradingInfra"];
  opsWaitMs?: number;
  opsFresh?: boolean;
}) {
  return resolveAutoTradingSurface({
    authPhase: partial.authPhase ?? "AUTH_READY",
    opsQuery: partial.opsQuery ?? "success",
    hasOpsData: partial.hasOpsData ?? true,
    tradingInfra: partial.tradingInfra ?? "TRADING_HEALTHY",
    opsWaitMs: partial.opsWaitMs,
    opsFresh: partial.opsFresh,
  });
}

// 1. Normal authenticated load
{
  const phase = resolveAuthPhase({
    loading: false,
    hasToken: true,
    hasUser: true,
    meStatus: "success",
  });
  assert.equal(phase, "AUTH_READY");
  assert.equal(canIssueProtectedOps(phase, true), true);
  const s = surface({});
  assert.equal(s.surface, "READY");
  assert.equal(s.blockNewEntries, false);
  assert.equal(s.haltsAutonomousTrading, false);
  assert.equal(s.reportGatewayDisconnected, false);
}

// 2. Auth bootstrap delay — stale UI must not fire protected ops
{
  const phase = resolveAuthPhase({
    loading: true,
    hasToken: true,
    hasUser: false,
    meStatus: "idle",
  });
  assert.equal(phase, "AUTH_LOADING");
  assert.equal(canIssueProtectedOps(phase, true), false);
  assert.equal(isAuthenticatedPhase(phase, false), false);
  const s = surface({ authPhase: "AUTH_LOADING", opsQuery: "idle", hasOpsData: false });
  assert.equal(s.surface, "AUTHENTICATING");
  assert.notEqual(s.surface, "UNAVAILABLE");
}

// 3. /auth/me timeout with token — AUTH_TIMEOUT, ops allowed, not signed out
{
  const phase = resolveAuthPhase({
    loading: false,
    hasToken: true,
    hasUser: true,
    meStatus: "timeout",
  });
  assert.equal(phase, "AUTH_TIMEOUT");
  assert.equal(canIssueProtectedOps(phase, true), true);
  assert.equal(isAuthenticatedPhase(phase, true), true);
  const s = surface({
    authPhase: "AUTH_TIMEOUT",
    opsQuery: "loading",
    hasOpsData: false,
  });
  assert.equal(s.surface, "LOADING_OPS");
  assert.equal(s.reportMt5Disconnected, false);
  assert.doesNotMatch(autoTradingSurfaceCopy(s).detail, /Waiting for authenticated ops data/);
}

// 4. API timeout
{
  const s = surface({
    opsQuery: "timeout",
    hasOpsData: false,
    tradingInfra: "UNKNOWN",
  });
  assert.equal(s.surface, "DEGRADED");
  assert.equal(resolveApiPhase({ opsQuery: "timeout", infra: "UNKNOWN" }), "API_DEGRADED");
  assert.equal(s.reportGatewayDisconnected, false);
}

// 5. Token refresh — one retry only
{
  assert.equal(
    shouldAttemptTokenRefresh({ status: 401, authEnabled: true, alreadyRetried: false }),
    true,
  );
  assert.equal(
    shouldAttemptTokenRefresh({ status: 401, authEnabled: true, alreadyRetried: true }),
    false,
  );
  assert.equal(
    shouldAttemptTokenRefresh({ status: 200, authEnabled: true, alreadyRetried: false }),
    false,
  );
}

// 6. Token expired → AUTH_REQUIRED, not broker disconnected
{
  const phase = resolveAuthPhase({
    loading: false,
    hasToken: false,
    hasUser: false,
    meStatus: "unauthorized",
  });
  assert.equal(phase, "AUTH_REQUIRED");
  const s = surface({
    authPhase: "AUTH_REQUIRED",
    opsQuery: "unauthorized",
    hasOpsData: false,
  });
  assert.equal(s.surface, "AUTH_REQUIRED");
  assert.equal(s.reportBrokerDisconnected, false);
  assert.match(autoTradingSurfaceCopy(s).detail, /Sign in again/i);
  assert.doesNotMatch(autoTradingSurfaceCopy(s).detail, /Gateway|MT5|broker disconnect/i);
}

// 7. Duplicate first-load GETs share one inflight
{
  assert.equal(shouldDedupeGet("/auth/me"), true);
  assert.equal(shouldDedupeGet("/api/v1/health/trading-components"), true);
  assert.equal(shouldDedupeGet("/ite/ops/auto-trading"), true);
  assert.equal(shouldDedupeGet("/ite/ops/control-center"), true);
  assert.equal(shouldDedupeGet("/ite/ops/launch-readiness"), true);
  assert.equal(shouldDedupeGet("/ite/ops/audit?limit=60"), true);
  assert.equal(shouldDedupeGet("/execution/journal?limit=80"), true);
  assert.equal(shouldDedupeGet("/mission-control/dashboard"), true);
  assert.equal(shouldDedupeGet("/portfolio"), true);
  assert.equal(shouldDedupeGet("/positions"), true);
  assert.equal(shouldDedupeGet("/positions?symbol=XAUUSD_i"), true);
  assert.equal(shouldDedupeGet("/orders"), true);
  assert.equal(shouldDedupeGet("/history"), true);
}

// 8. trading-components healthy + ops timeout → infra READY, ops DEGRADED
{
  assert.equal(
    resolveTradingInfraState({ gatewayOk: true, mt5Ok: true, omsOk: true }),
    "TRADING_HEALTHY",
  );
  const s = surface({
    opsQuery: "timeout",
    hasOpsData: false,
    tradingInfra: "TRADING_HEALTHY",
  });
  assert.equal(s.surface, "DEGRADED");
  assert.equal(s.tradingInfra, "TRADING_HEALTHY");
  assert.match(autoTradingSurfaceCopy(s).detail, /healthy/i);
  assert.doesNotMatch(autoTradingSurfaceCopy(s).title, /unavailable/i);
}

// 9. API timeout != Gateway disconnected
{
  const s = surface({ opsQuery: "timeout", hasOpsData: false, tradingInfra: "UNKNOWN" });
  assert.equal(s.reportGatewayDisconnected, false);
  assert.notEqual(s.surface, "UNAVAILABLE");
}

// 10. Auth timeout != MT5 disconnected
{
  const s = surface({
    authPhase: "AUTH_TIMEOUT",
    opsQuery: "timeout",
    hasOpsData: false,
    tradingInfra: "TRADING_HEALTHY",
  });
  assert.equal(s.reportMt5Disconnected, false);
  assert.equal(s.surface, "DEGRADED");
}

// 11. Stale session != broker disconnected
{
  const s = surface({
    authPhase: "AUTH_REQUIRED",
    opsQuery: "unauthorized",
    hasOpsData: false,
    tradingInfra: "UNKNOWN",
  });
  assert.equal(s.reportBrokerDisconnected, false);
  assert.equal(s.surface, "AUTH_REQUIRED");
}

// Timeouts after vs before
assert.equal(defaultTimeoutForPath("/auth/me"), API_AUTH_TIMEOUT_MS);
assert.equal(API_AUTH_TIMEOUT_MS, 40_000);
assert.equal(defaultTimeoutForPath("/health/live"), API_HEALTH_LIVE_TIMEOUT_MS);
assert.equal(defaultTimeoutForPath("/health"), API_HEALTH_TIMEOUT_MS);
assert.equal(defaultTimeoutForPath("/weltrade/health"), 45_000);
assert.ok(API_HEALTH_LIVE_TIMEOUT_MS < 8_000);
assert.ok(sessionBootBudgetMs() > API_AUTH_TIMEOUT_MS);
assert.equal(classifyOpsFailure({ code: "timeout", status: 408 }), "timeout");
assert.equal(classifyOpsFailure({ status: 401 }), "unauthorized");
assert.equal(classifyOpsFailure({ status: 403, code: "insufficient_role" }), "forbidden");

// Authenticated session ready → LOADING_OPS, never the old auth-wait copy
{
  const s = surface({
    authPhase: "AUTH_READY",
    opsQuery: "loading",
    hasOpsData: false,
    tradingInfra: "TRADING_HEALTHY",
  });
  assert.equal(s.surface, "LOADING_OPS");
  assert.match(autoTradingSurfaceCopy(s).detail, /healthy/i);
  assert.doesNotMatch(autoTradingSurfaceCopy(s).detail, /Waiting for authenticated ops data/);
}

// API slow but healthy infra while still in-flight → stay LOADING_OPS
{
  const s = surface({
    authPhase: "AUTH_READY",
    opsQuery: "loading",
    hasOpsData: false,
    tradingInfra: "TRADING_HEALTHY",
    opsWaitMs: OPS_SLOW_MS,
  });
  assert.equal(s.surface, "LOADING_OPS");
  assert.equal(s.blockNewEntries, false);
  assert.equal(s.haltsAutonomousTrading, false);
  assert.equal(s.tradingInfra, "TRADING_HEALTHY");
  assert.equal(s.reportGatewayDisconnected, false);
}

// Ops timeout with healthy infra → DEGRADED advisory, must not halt trades
{
  const s = surface({
    authPhase: "AUTH_READY",
    opsQuery: "timeout",
    hasOpsData: false,
    tradingInfra: "TRADING_HEALTHY",
  });
  assert.equal(s.surface, "DEGRADED");
  assert.equal(s.blockNewEntries, false);
  assert.equal(s.haltsAutonomousTrading, false);
  assert.equal(s.reportGatewayDisconnected, false);
  assert.match(autoTradingSurfaceCopy(s).detail, /does not halt new entries/i);
}

// Recovery: timeout then success → READY, entries unblocked
{
  const delayed = surface({
    opsQuery: "timeout",
    hasOpsData: false,
    tradingInfra: "TRADING_HEALTHY",
  });
  assert.equal(delayed.surface, "DEGRADED");
  assert.equal(delayed.blockNewEntries, false);
  const recovered = surface({
    opsQuery: "success",
    hasOpsData: true,
    opsFresh: true,
    tradingInfra: "TRADING_HEALTHY",
  });
  assert.equal(recovered.surface, "READY");
  assert.equal(recovered.blockNewEntries, false);
}

// Stale last-known-good during load → DEGRADED advisory, must not halt
{
  const s = surface({
    authPhase: "AUTH_READY",
    opsQuery: "loading",
    hasOpsData: true,
    opsFresh: false,
    tradingInfra: "TRADING_HEALTHY",
  });
  assert.equal(s.surface, "DEGRADED");
  assert.equal(s.blockNewEntries, false);
  assert.equal(s.haltsAutonomousTrading, false);
}

// Last-known-good ops telemetry is bounded and not fabricated
{
  resetOpsTelemetryLastGood();
  rememberOpsTelemetry({ status: "enabled", execution_enabled: true }, 1_000);
  const hit = readOpsTelemetry(1_000 + 30_000);
  assert.equal(hit?.payload.status, "enabled");
  assert.equal(hit?.stale, true);
  assert.equal(readOpsTelemetry(1_000 + 6 * 60_000), null);
  resetOpsTelemetryLastGood();
}

// In-flight ops with last-known-good stays on screen; telemetry stale is advisory
{
  const s = surface({
    authPhase: "AUTH_READY",
    opsQuery: "loading",
    hasOpsData: true,
    opsFresh: false,
    tradingInfra: "TRADING_HEALTHY",
  });
  assert.equal(s.surface, "DEGRADED");
  assert.equal(s.blockNewEntries, false);
  assert.equal(s.haltsAutonomousTrading, false);
}

// Hard infra (Gateway/MT5/OMS down) still hard-blocks
{
  const s = surface({
    authPhase: "AUTH_READY",
    opsQuery: "success",
    hasOpsData: true,
    opsFresh: true,
    tradingInfra: "TRADING_DEGRADED",
  });
  assert.equal(s.surface, "DEGRADED");
  assert.equal(s.blockNewEntries, true);
  assert.equal(s.haltsAutonomousTrading, true);
  assert.match(autoTradingSurfaceCopy(s).detail, /hard-blocked/i);
}

console.log("bootstrap.test.ts: ok");
