"use client";

import { useEffect, useRef } from "react";
import { ApiError, apiFetch } from "@/lib/api/client";
import { clearRefCode, pendingRefCode, rememberRefCode } from "@/lib/referrals/ref-store";

/** Public pages: remember ?ref=CODE from a shared link (no network call). */
export function ReferralCapture() {
  useEffect(() => {
    try {
      const ref = new URLSearchParams(window.location.search).get("ref");
      if (ref) rememberRefCode(ref);
    } catch {
      /* ignore */
    }
  }, []);
  return null;
}

/**
 * Signed-in app: attribute a remembered code once. The server decides
 * (self-referral, existing customer, duplicates and rate limits are refused);
 * the code is forgotten after any definitive answer.
 */
export function ReferralAutoAttribute() {
  const sent = useRef(false);
  useEffect(() => {
    try {
      const ref = new URLSearchParams(window.location.search).get("ref");
      if (ref) rememberRefCode(ref);
    } catch {
      /* ignore */
    }
    const code = pendingRefCode();
    if (!code || sent.current) return;
    sent.current = true;
    apiFetch<Record<string, unknown>>("/referrals/attribute", { method: "POST", body: { code } })
      .then(() => clearRefCode())
      .catch((err: unknown) => {
        // Disabled / invalid is definitive. Keep the code when not signed in yet
        // (401/403), rate-limited (429) or on network/5xx errors.
        if (err instanceof ApiError && [400, 404, 409, 422].includes(err.status)) clearRefCode();
        sent.current = false;
      });
  }, []);
  return null;
}
