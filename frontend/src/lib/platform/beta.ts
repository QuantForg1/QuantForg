/**
 * Closed-beta / ops mode controls via env (no redeploy toggles except invite unlock).
 *
 * NEXT_PUBLIC_BETA_MODE=true → require invite unlock
 * NEXT_PUBLIC_BETA_INVITE_CODE=... → shared invite code (never log the code value in audit metadata)
 * NEXT_PUBLIC_MAINTENANCE_MODE=true → show maintenance gate
 * NEXT_PUBLIC_READ_ONLY_MODE=true → block mutating trading actions in UI
 */

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
  const inviteConfigured = Boolean(process.env.NEXT_PUBLIC_BETA_INVITE_CODE?.trim());
  const unlocked =
    typeof window === "undefined"
      ? !betaMode
      : !betaMode || localStorage.getItem(UNLOCK_KEY) === "1";
  return {
    betaMode,
    unlocked,
    maintenanceMode: process.env.NEXT_PUBLIC_MAINTENANCE_MODE === "true",
    readOnlyMode: process.env.NEXT_PUBLIC_READ_ONLY_MODE === "true",
    inviteConfigured,
  };
}

export function unlockBeta(code: string): boolean {
  const expected = process.env.NEXT_PUBLIC_BETA_INVITE_CODE?.trim();
  if (!expected) return true;
  if (code.trim() !== expected) return false;
  if (typeof window !== "undefined") localStorage.setItem(UNLOCK_KEY, "1");
  return true;
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
