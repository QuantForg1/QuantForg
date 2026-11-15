"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import {
  getAccessToken,
  saveSession,
  setMfaPending,
  type AuthSession,
} from "@/lib/auth/session";
import { useAuth } from "@/providers/auth-provider";

export default function MfaChallengePage() {
  const router = useRouter();
  const { refreshMe } = useAuth();
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState("");
  const [factorId, setFactorId] = useState<string | null>(null);
  const [challengeId, setChallengeId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [mode, setMode] = useState<"totp" | "recovery">("totp");
  const [error, setError] = useState<string | null>(null);
  const bootstrapped = useRef(false);

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    void (async () => {
      try {
        const status = await authApi.mfaStatus();
        const factor = (status.factors || []).find((f) => {
          const st = String(f.status || "").toLowerCase();
          const type = String(f.factor_type || "").toLowerCase();
          return st === "verified" && (type === "totp" || !type);
        });
        const id = factor ? String(factor.id || "") : "";
        if (!id) {
          router.replace("/dashboard");
          return;
        }
        setFactorId(id);
        const challenge = await authApi.mfaChallenge(id);
        setChallengeId(challenge.challenge_id);
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "Could not start MFA challenge",
        );
      }
    })();
  }, [router]);

  const verifyTotp = async () => {
    if (!factorId || !/^\d{6}$/.test(code) || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      let challenge = challengeId;
      if (!challenge) {
        const created = await authApi.mfaChallenge(factorId);
        challenge = created.challenge_id;
        setChallengeId(challenge);
      }
      const result = await authApi.mfaVerify({
        factor_id: factorId,
        challenge_id: challenge,
        code,
      });
      const session =
        "access_token" in result
          ? (result as AuthSession)
          : (result as { session: AuthSession }).session;
      saveSession(session, { remember: true });
      setMfaPending(false);
      await refreshMe();
      toast.success("Verification complete");
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Invalid authenticator code");
      setChallengeId(null);
    } finally {
      setSubmitting(false);
    }
  };

  const verifyRecovery = async () => {
    if (!recovery.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const session = await authApi.mfaRecoveryConsume(recovery.trim());
      saveSession(session, { remember: true });
      setMfaPending(false);
      await refreshMe();
      toast.success("Recovery code accepted");
      router.replace("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Invalid or already-used recovery code",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell
      title="Two-factor authentication"
      subtitle="Enter the code from your authenticator app to continue."
    >
      <div className="space-y-4">
        {mode === "totp" ? (
          <>
            <div className="space-y-2">
              <Label htmlFor="mfa-code">Authenticator code</Label>
              <Input
                id="mfa-code"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="000000"
              />
            </div>
            <Button
              className="qf-btn-hot h-11 w-full"
              disabled={submitting || !/^\d{6}$/.test(code)}
              onClick={() => void verifyTotp()}
            >
              {submitting ? "Verifying…" : "Verify"}
            </Button>
            <button
              type="button"
              className="w-full text-center text-sm text-[var(--accent)]"
              onClick={() => setMode("recovery")}
            >
              Use a recovery code
            </button>
          </>
        ) : (
          <>
            <div className="space-y-2">
              <Label htmlFor="recovery-code">Recovery code</Label>
              <Input
                id="recovery-code"
                autoComplete="off"
                value={recovery}
                onChange={(e) => setRecovery(e.target.value.toUpperCase())}
                placeholder="XXXXX-XXXXX"
              />
            </div>
            <Button
              className="qf-btn-hot h-11 w-full"
              disabled={submitting || !recovery.trim()}
              onClick={() => void verifyRecovery()}
            >
              {submitting ? "Verifying…" : "Continue with recovery code"}
            </Button>
            <button
              type="button"
              className="w-full text-center text-sm text-[var(--accent)]"
              onClick={() => setMode("totp")}
            >
              Use authenticator code
            </button>
          </>
        )}
        {error ? (
          <p className="text-center text-sm text-[var(--danger)]" role="alert">
            {error}
          </p>
        ) : null}
        <p className="text-center text-sm text-[var(--fg-muted)]">
          <Link href="/login" className="text-[var(--accent)]">
            Back to sign in
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}
