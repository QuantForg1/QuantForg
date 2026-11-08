"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { BrandMark } from "@/components/brand/brand-logo";
import { authApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { saveSession } from "@/lib/auth/session";
import { getClientAppOrigin } from "@/lib/env";

/**
 * OAuth return path for Supabase Auth (Google).
 * Expects ?code=… (PKCE). Cancelled attempts show a recoverable error.
 */
function OAuthCallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [message, setMessage] = useState("Completing Google sign-in…");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function complete() {
      const error = params.get("error");
      const errorDescription = params.get("error_description");
      if (error) {
        if (!cancelled) {
          setFailed(true);
          setMessage(
            error === "access_denied"
              ? "Google sign-in was cancelled. You can try again or use email and password."
              : errorDescription || `Google sign-in failed (${error}).`,
          );
        }
        return;
      }

      const code = params.get("code");
      if (!code) {
        if (!cancelled) {
          setFailed(true);
          setMessage(
            "Missing authorization code. Start Google sign-in again from the login page.",
          );
        }
        return;
      }

      try {
        const redirectTo = `${getClientAppOrigin()}/auth/callback`;
        const session = await authApi.oauthCallback(code, redirectTo);
        saveSession(session, { remember: true });
        if (!cancelled) {
          setMessage("Signed in. Redirecting…");
          router.replace("/dashboard");
        }
      } catch (err) {
        if (!cancelled) {
          setFailed(true);
          setMessage(
            err instanceof ApiError
              ? err.message
              : err instanceof Error
                ? err.message
                : "Could not complete Google sign-in.",
          );
        }
      }
    }

    void complete();
    return () => {
      cancelled = true;
    };
  }, [params, router]);

  return (
    <main
      id="main-content"
      className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[var(--bg)] px-4 text-center"
      tabIndex={-1}
    >
      <BrandMark size={56} priority />
      <h1 className="text-xl font-semibold tracking-tight">
        {failed ? "Sign-in interrupted" : "Connecting Google"}
      </h1>
      <p className="max-w-md text-sm leading-relaxed text-[var(--fg-muted)]">{message}</p>
      {failed ? (
        <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/login"
            className="qf-btn-primary inline-flex h-10 items-center rounded-[var(--radius-sm)] px-4 text-sm font-semibold"
          >
            Back to sign in
          </Link>
          <Link
            href="/register"
            className="inline-flex h-10 items-center rounded-[var(--radius-sm)] border border-[var(--border)] px-4 text-sm font-medium"
          >
            Create account
          </Link>
        </div>
      ) : null}
    </main>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-[var(--bg)]">
          <p className="text-sm text-[var(--fg-muted)]">Loading…</p>
        </main>
      }
    >
      <OAuthCallbackInner />
    </Suspense>
  );
}
