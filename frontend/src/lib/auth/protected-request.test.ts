/**
 * Protected request + Mission Control timeline classification.
 * Run: node --experimental-strip-types src/lib/auth/protected-request.test.ts
 */
import assert from "node:assert/strict";
import { ApiError } from "../api/client";
import { shouldDedupeGet } from "../api/request-policy";
import { canIssueProtectedOps, resolveAuthPhase } from "./bootstrap";
import {
  classifyProtectedFailure,
  copyContainsSecretLeak,
  protectedFailureCopy,
  resolveBearerAuthorization,
} from "./protected-request";
import { mergeTimelineEvents } from "../ops/mission-timeline";

{
  const ready = resolveAuthPhase({
    loading: false,
    hasToken: true,
    hasUser: true,
    meStatus: "success",
  });
  assert.equal(ready, "AUTH_READY");
  assert.equal(canIssueProtectedOps(ready, true), true);
}

{
  const loading = resolveAuthPhase({
    loading: true,
    hasToken: true,
    hasUser: false,
    meStatus: "idle",
  });
  assert.equal(loading, "AUTH_LOADING");
  assert.equal(canIssueProtectedOps(loading, true), false);
  assert.equal(
    classifyProtectedFailure({ authPhase: loading, opsReady: false, error: null }),
    "AUTH_BOOTSTRAP_PENDING",
  );
  assert.match(protectedFailureCopy("AUTH_BOOTSTRAP_PENDING").title, /Authenticating/i);
}

{
  const required = resolveAuthPhase({
    loading: false,
    hasToken: false,
    hasUser: false,
    meStatus: "unauthorized",
  });
  assert.equal(required, "AUTH_REQUIRED");
  assert.equal(
    classifyProtectedFailure({ authPhase: required, opsReady: false, error: null }),
    "AUTH_REQUIRED",
  );
}

{
  const stored = "sess_test_token";
  const attached = resolveBearerAuthorization({
    auth: true,
    storedToken: stored,
  });
  assert.equal(attached.rejectCode, null);
  assert.equal(attached.header?.startsWith("Bearer "), true);
  assert.equal(copyContainsSecretLeak(protectedFailureCopy("AUTH_REQUIRED").detail), false);
  assert.equal(copyContainsSecretLeak("Authorization: Bearer eyJhbGciOi.fake.sig"), true);

  const missing = resolveBearerAuthorization({ auth: true, storedToken: null });
  assert.equal(missing.header, null);
  assert.equal(missing.rejectCode, "auth_bootstrap_pending");

  const pub = resolveBearerAuthorization({ auth: false, storedToken: stored });
  assert.equal(pub.header, null);
  assert.equal(pub.rejectCode, null);
}

{
  assert.equal(
    classifyProtectedFailure({
      authPhase: "AUTH_READY",
      opsReady: true,
      error: new ApiError("Missing bearer access token", 401, "missing_token"),
    }),
    "AUTH_REQUIRED",
  );
  assert.doesNotMatch(protectedFailureCopy("AUTH_REQUIRED").detail, /Missing bearer access token/);
  assert.equal(
    classifyProtectedFailure({
      authPhase: "AUTH_READY",
      opsReady: true,
      error: new ApiError("Authentication failed", 401, "authentication_failed"),
    }),
    "AUTH_EXPIRED",
  );
  assert.match(protectedFailureCopy("AUTH_EXPIRED").title, /Session expired/i);
  assert.equal(
    classifyProtectedFailure({
      authPhase: "AUTH_READY",
      opsReady: true,
      error: new ApiError("Insufficient role", 403, "insufficient_role"),
    }),
    "FORBIDDEN",
  );
  assert.equal(
    classifyProtectedFailure({
      authPhase: "AUTH_READY",
      opsReady: true,
      error: new ApiError("Unable to reach", 0, "network_error"),
    }),
    "NETWORK_ERROR",
  );
  assert.match(protectedFailureCopy("NETWORK_ERROR").title, /unavailable/i);
}

{
  const events = mergeTimelineEvents(
    { items: [{ action: "filled", at: "2026-08-18T12:00:00Z", request_id: "r1" }] },
    { entries: [{ action: "scan", at: "2026-08-18T12:01:00Z" }] },
  );
  assert.equal(events.length, 2);
  assert.equal(events[0]?.title, "scan");
  const empty = mergeTimelineEvents({ items: [] }, { entries: [] });
  assert.equal(empty.length, 0);
}

{
  assert.equal(shouldDedupeGet("/execution/journal?limit=80"), true);
  assert.equal(shouldDedupeGet("/ite/ops/audit?limit=60"), true);
  assert.equal(shouldDedupeGet("/mission-control/dashboard"), true);
  assert.equal(shouldDedupeGet("/ite/ops/auto-trading"), true);
}

console.log("protected-request.test.ts: ok");
