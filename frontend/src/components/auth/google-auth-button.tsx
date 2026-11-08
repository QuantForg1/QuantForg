"use client";

import { useState } from "react";
import { authApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { getClientAppOrigin } from "@/lib/env";

/**
 * Google OAuth via existing Railway auth API → Supabase Auth.
 * Requires Google provider + redirect URLs configured in Supabase / Google Cloud.
 * Surfaces real OAuth/config errors only — no static marketing copy under the button.
 */
export function GoogleAuthButton() {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function startGoogle() {
    setBusy(true);
    setStatus(null);
    try {
      const redirectTo = `${getClientAppOrigin()}/auth/callback`;
      const { url } = await authApi.oauthStart("google", redirectTo);
      if (!url) {
        throw new Error("Google sign-in did not return a redirect URL.");
      }
      window.location.assign(url);
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Google sign-in is unavailable.";
      const configuredHint =
        /oauth|provider|not configured|disabled|redirect/i.test(message)
          ? " Confirm Google is enabled in Supabase Auth and the redirect URL includes this site’s /auth/callback."
          : " You can still use email and password.";
      setStatus(`${message}${configuredHint}`);
      setBusy(false);
    }
  }

  return (
    <div className="mt-5">
      <div className="relative my-4 text-center text-xs text-[var(--fg-subtle)]">
        <span className="relative z-10 bg-[var(--surface)] px-3">or continue with</span>
        <span className="absolute inset-x-0 top-1/2 border-t border-[var(--border)]" aria-hidden />
      </div>
      <button
        type="button"
        onClick={() => void startGoogle()}
        disabled={busy}
        aria-describedby={status ? "google-auth-status" : undefined}
        className="flex h-11 w-full items-center justify-center gap-2 rounded-[var(--radius-sm)] border border-[var(--border)] bg-transparent text-sm font-medium text-[var(--fg)] transition-colors hover:bg-[var(--surface-2)] disabled:cursor-wait disabled:opacity-70"
      >
        <GoogleGlyph />
        {busy ? "Redirecting to Google…" : "Continue with Google"}
      </button>
      {status ? (
        <p
          id="google-auth-status"
          className="mt-2 text-center text-xs leading-relaxed text-[var(--danger)]"
          role="alert"
        >
          {status}
        </p>
      ) : null}
    </div>
  );
}

function GoogleGlyph() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4" focusable="false">
      <path
        fill="#EA4335"
        d="M12 10.2v3.6h5.1c-.2 1.2-.9 2.2-1.9 2.9l3.1 2.4c1.8-1.7 2.8-4.1 2.8-7 0-.7-.1-1.3-.2-1.9H12z"
      />
      <path
        fill="#34A853"
        d="M6.6 14.3l-.8.6-2.8 2.2C4.6 20.1 8 22 12 22c2.7 0 5-.9 6.7-2.4l-3.1-2.4c-.9.6-2 .9-3.6.9-2.8 0-5.1-1.9-6-4.4z"
      />
      <path
        fill="#4A90E2"
        d="M3 7.1C2.4 8.3 2 9.6 2 11s.4 2.7 1 3.9c0 .1 3.6-2.8 3.6-2.8-.2-.6-.3-1.2-.3-1.9s.1-1.3.3-1.9L3 7.1z"
      />
      <path
        fill="#FBBC05"
        d="M12 5.2c1.5 0 2.8.5 3.8 1.5l2.8-2.8C16.9 2.3 14.7 1.4 12 1.4 8 1.4 4.6 3.3 3 6.5l3.6 2.8c.9-2.5 3.2-4.1 5.4-4.1z"
      />
    </svg>
  );
}
