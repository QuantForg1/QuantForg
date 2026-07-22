/**
 * Closed-beta / ops mode controls.
 *
 * NEXT_PUBLIC_BETA_MODE=true → require invite unlock (public flag only)
 * Invite secret lives server-side as BETA_INVITE_CODE (never NEXT_PUBLIC_*)
 * NEXT_PUBLIC_MAINTENANCE_MODE / NEXT_PUBLIC_READ_ONLY_MODE → UI gates only
 */

import { apiFetch } from "@/lib/api/client";

const UNLOCK_KEY = "qf.beta.unlocked.v1";

export type BetaState = {
  betaMode: boolean;
  unlocked: boolean;
  maintenanceMode: boolean;
  readOnlyMode: boolean;
  inviteConfigured: boolean;
};

export function getBetaState(): BetaState {
  const betaMode = process.env.NEXT_PUBLIC_BETA_MODE === "true";
  const unlocked =
    typeof window === "undefined"
      ? !betaMode
      : !betaMode || localStorage.getItem(UNLOCK_KEY) === "1";
  return {
    betaMode,
    unlocked,
    maintenanceMode: process.env.NEXT_PUBLIC_MAINTENANCE_MODE === "true",
    readOnlyMode: process.env.NEXT_PUBLIC_READ_ONLY_MODE === "true",
    // Invite secret is never in the client bundle; status comes from API when needed.
    inviteConfigured: betaMode,
  };
}

/** Verify invite against server-only BETA_INVITE_CODE. */
export async function unlockBeta(code: string): Promise<boolean> {
  const trimmed = code.trim();
  if (!trimmed) return false;
  try {
    await apiFetch<{ ok: boolean }>("/beta/unlock", {
      method: "POST",
      auth: false,
      body: { code: trimmed },
    });
    if (typeof window !== "undefined") localStorage.setItem(UNLOCK_KEY, "1");
    return true;
  } catch {
    return false;
  }
}

export function lockBeta() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(UNLOCK_KEY);
}

export function isBetaGateBlocking() {
  const s = getBetaState();
  return s.betaMode && !s.unlocked;
}

export function isMaintenanceBlocking() {
  return getBetaState().maintenanceMode;
}

export function isReadOnlyMode() {
  return getBetaState().readOnlyMode;
}
