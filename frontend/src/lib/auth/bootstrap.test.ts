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
  defaultTimeoutForPath,
  sessionBootBudgetMs,
  shouldAttemptTokenRefresh,
  shouldDedupeGet,
} from "../api/request-policy";
import {
  autoTradingSurfaceCopy,
  classifyOpsFailure,
  resolveAutoTradingSurface,
  resolveApiPhase,
  resolveTradingInfraState,
} from "../ops/auto-trading-surface";

function surface(partial: {
  authPhase?: Parameters<typeof resolveAutoTradingSurface>[0]["authPhase"];
  opsQuery?: Parameters<typeof resolveAutoTradingSurface>[0]["opsQuery"];
  hasOpsData?: boolean;
  tradingInfra?: Parameters<typeof resolveAutoTradingSurface>[0]["tradingInfra"];
}) {
  return resolveAutoTradingSurface({
    authPhase: partial.authPhase ?? "AUTH_READY",
    opsQuery: partial.opsQuery ?? "success",
    hasOpsData: partial.hasOpsData ?? true,
    tradingInfra: partial.tradingInfra ?? "TRADING_HEALTHY",
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
  assert.equal(s.surface, "LOADING");
  assert.equal(s.reportMt5Disconnected, false);
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
  assert.equal(shouldDedupeGet("/portfolio"), false);
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
assert.ok(sessionBootBudgetMs() > API_AUTH_TIMEOUT_MS);
assert.equal(classifyOpsFailure({ code: "timeout", status: 408 }), "timeout");
assert.equal(classifyOpsFailure({ status: 401 }), "unauthorized");
assert.equal(classifyOpsFailure({ status: 403, code: "insufficient_role" }), "forbidden");

console.log("bootstrap.test.ts: ok");
