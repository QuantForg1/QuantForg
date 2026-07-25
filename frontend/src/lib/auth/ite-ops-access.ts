/**
 * ITE ops permission source — must match backend require_roles(OWNER, ADMIN).
 *
 * Backend: app/presentation/dependencies/auth.py → require_roles
 *          + public.users.role (AuthUserDTO.role / /auth/me)
 * Roles:   app/domain/enums/user.py → UserRole.OWNER|ADMIN = "owner"|"admin"
 * Ops:     app/domain/institutional_trading/operations/models.py → OPERATOR_ROLES
 */

import { ApiError } from "@/lib/api/client";
import type { AuthUser } from "@/lib/auth/session";

/** Same strings as backend UserRole.OWNER / UserRole.ADMIN / OPERATOR_ROLES. */
export const ITE_OPS_ROLES = ["owner", "admin"] as const;

export type IteOpsRole = (typeof ITE_OPS_ROLES)[number];

export function normalizePlatformRole(
  role: string | null | undefined,
): string {
  return String(role ?? "")
    .trim()
    .toLowerCase();
}

/** True when platform user.role is owner|admin (not org membership role). */
export function canAccessIteOps(
  user: Pick<AuthUser, "role"> | null | undefined,
): boolean {
  const role = normalizePlatformRole(user?.role);
  return (ITE_OPS_ROLES as readonly string[]).includes(role);
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
      `${surface} unavailable — OWNER/ADMIN required ` +
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
      `${surface} unavailable — OWNER/ADMIN required ` +
      `(user=${user.id} role=${role} required=${ITE_OPS_ROLES.join("|")}).`
    );
  }
  if (api) {
    return `${surface} unavailable — ${api.message} (${api.code || api.status}).`;
  }
  return `${surface} unavailable — OWNER/ADMIN required for ITE ops controls.`;
}
