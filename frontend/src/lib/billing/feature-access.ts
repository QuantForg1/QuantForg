/**
 * Paid-feature access for the UI. Server truth comes from
 * `billing/me.robot_access.allowed` (owner/admin are allowed there too).
 * The API enforces the same rule with HTTP 402, so this is presentation only.
 */
export type FeatureAccess = "checking" | "open" | "locked" | "unknown";

export function signalsAccess(input: {
  loading: boolean;
  error: boolean;
  robotAccess: Record<string, unknown>;
}): FeatureAccess {
  if (input.loading) return "checking";
  if (input.error) return "unknown";
  return input.robotAccess.allowed === true ? "open" : "locked";
}

/** True when an API error means "this feature needs a paid plan". */
export function isSubscriptionRequiredError(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const e = err as { status?: unknown; code?: unknown; details?: unknown };
  if (e.status === 402) return true;
  const details = (e.details ?? {}) as { detail?: { code?: unknown } };
  return e.code === "subscription_required" || details.detail?.code === "subscription_required";
}
