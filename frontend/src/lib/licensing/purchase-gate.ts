/**
 * Client-side purchase entitlement gate (UI-only until payment is integrated).
 * Does not touch auth APIs or backend billing.
 */

export const PURCHASE_GATE_KEY = "qf_lifetime_purchase_ok";
export const PURCHASE_GATE_VALUE = "1";

export function markLifetimePurchaseComplete(): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(PURCHASE_GATE_KEY, PURCHASE_GATE_VALUE);
  } catch {
    /* private mode / blocked storage — register page will re-check */
  }
}

export function hasLifetimePurchaseEntitlement(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return sessionStorage.getItem(PURCHASE_GATE_KEY) === PURCHASE_GATE_VALUE;
  } catch {
    return false;
  }
}
