/**
 * ITE ops UI gate. The server is authoritative: only the verified designated
 * owner keeps OWNER/ADMIN. A matching email in the browser is not a grant.
 */

import { ApiError } from "@/lib/api/client";
import type { AuthUser } from "@/lib/auth/session";

/** Platform owner role. Other accounts cannot become owner from the client. */
export const DESIGNATED_OWNER_EMAIL = "p7provider@gmail.com";
export const ITE_OPS_ROLES = ["owner"] as const;

export type IteOpsRole = (typeof ITE_OPS_ROLES)[number];

export function normalizePlatformRole(
  role: string | null | undefined,
): string {
  return String(role ?? "")
    .trim()
    .toLowerCase();
}

/** True only for the designated platform owner identity from /auth/me. */
export function canAccessIteOps(
  user: Pick<AuthUser, "role" | "email"> | null | undefined,
): boolean {
  const role = normalizePlatformRole(user?.role);
  const email = String(user?.email ?? "")
    .trim()
    .toLowerCase();
  return role === "owner" && email === DESIGNATED_OWNER_EMAIL;
}

/**
 * Human message for ITE ops denial — never blame OWNER/ADMIN for auth/timeouts.
 */
export function iteOpsAccessDeniedMessage(
  user: AuthUser | null | undefined,
  error?: unknown,
  surface = "ITE ops",
): string {
  const role = normalizePlatformRole(user?.role) || "unknown";
  const api = error instanceof ApiError ? error : null;
  const details =
    api?.details && typeof api.details === "object"
      ? (api.details as Record<string, unknown>)
      : {};
  const actual =
    typeof details.actual_role === "string"
      ? normalizePlatformRole(details.actual_role)
      : role;
  const required = Array.isArray(details.required_roles)
    ? details.required_roles.map(String).join("|")
    : ITE_OPS_ROLES.join("|");

  if (api?.code === "insufficient_role" || api?.status === 403) {
    return (
      `${surface} unavailable — verified platform owner required ` +
      `(user=${user?.id ?? "?"} role=${actual || "unknown"} required=${required}).`
    );
  }
  if (
    api?.code === "missing_token" ||
    api?.code === "authentication_failed" ||
    api?.status === 401
  ) {
    return `${surface} unavailable — sign in required (${api.code || "401"}).`;
  }
  if (user && !canAccessIteOps(user)) {
    return (
      `${surface} unavailable — verified platform owner required ` +
      `(user=${user.id} role=${role} required=${ITE_OPS_ROLES.join("|")}).`
    );
  }
  if (
    api?.code === "timeout" ||
    api?.status === 408 ||
    api?.code === "network_error"
  ) {
    return (
      `${surface} delayed — API did not respond in time. ` +
      `Trading connectivity is not inferred from this timeout.`
    );
  }
  if (api) {
    return `${surface} unavailable — ${api.message} (${api.code || api.status}).`;
  }
  return `${surface} unavailable — verified platform owner required.`;
}
