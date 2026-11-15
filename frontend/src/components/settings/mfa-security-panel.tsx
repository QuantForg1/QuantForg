"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { DeskSkeleton } from "@/components/desk/primitives";
import { authApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { saveSession, type AuthSession } from "@/lib/auth/session";
import { cn } from "@/lib/utils";

function factorIdOf(factor: Record<string, unknown>): string {
  return String(factor.id || factor.factor_id || "");
}

function isVerifiedTotp(factor: Record<string, unknown>): boolean {
  const status = String(factor.status || "").toLowerCase();
  const type = String(factor.factor_type || factor.factorType || "").toLowerCase();
  return status === "verified" && (type === "totp" || type === "");
}

export function MfaSecurityPanel() {
  const qc = useQueryClient();
  const statusQ = useQuery({
    queryKey: ["mfa-status"],
    queryFn: authApi.mfaStatus,
    retry: false,
  });

  const [enroll, setEnroll] = useState<{
    factor_id: string;
    qr_code: string;
    secret: string;
  } | null>(null);
  const [verifyCode, setVerifyCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);

  const factors = statusQ.data?.factors ?? [];
  const verified = factors.filter(isVerifiedTotp);
  const enabled = Boolean(statusQ.data?.enabled || verified.length > 0);
  const aal = statusQ.data?.aal;

  const startEnroll = useMutation({
    mutationFn: () => authApi.mfaEnroll(),
    onSuccess: (data) => {
      setEnroll({
        factor_id: data.factor_id,
        qr_code: data.qr_code,
        secret: data.secret,
      });
      setVerifyCode("");
      setRecoveryCodes(null);
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : "Could not start MFA enrollment");
    },
  });

  const confirmEnroll = async () => {
    if (!enroll || !/^\d{6}$/.test(verifyCode) || busy) return;
    setBusy(true);
    try {
      const challenge = await authApi.mfaChallenge(enroll.factor_id);
      const result = await authApi.mfaVerify({
        factor_id: enroll.factor_id,
        challenge_id: challenge.challenge_id,
        code: verifyCode,
        issue_recovery_codes: true,
      });
      if ("recovery_codes" in result && Array.isArray(result.recovery_codes)) {
        if (result.session) {
          saveSession(result.session as AuthSession, { remember: true });
        }
        setRecoveryCodes(result.recovery_codes);
      } else if ("access_token" in result) {
        saveSession(result as AuthSession, { remember: true });
      }
      setEnroll(null);
      setVerifyCode("");
      toast.success("Two-factor authentication enabled");
      await qc.invalidateQueries({ queryKey: ["mfa-status"] });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Invalid authenticator code");
    } finally {
      setBusy(false);
    }
  };

  const disable = async (factorId: string) => {
    if (busy) return;
    setBusy(true);
    try {
      await authApi.mfaUnenroll(factorId);
      toast.success("Two-factor authentication disabled");
      setRecoveryCodes(null);
      await qc.invalidateQueries({ queryKey: ["mfa-status"] });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not disable MFA");
    } finally {
      setBusy(false);
    }
  };

  const regenerate = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const result = await authApi.mfaRecoveryGenerate();
      setRecoveryCodes(result.recovery_codes);
      toast.success("New recovery codes generated. Store them securely.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not regenerate recovery codes");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="qf-card-interactive lg:col-span-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Two-factor authentication
          <Badge tone={enabled ? "success" : "neutral"}>
            {enabled ? "Enabled" : "Optional"}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {statusQ.isLoading ? (
          <DeskSkeleton rows={3} />
        ) : (
          <>
            <p className="text-sm text-[var(--fg-muted)]">
              Protect your account with an authenticator app (TOTP). Enrollment is optional and
              never forced for existing users.
            </p>
            {aal ? (
              <p className="text-xs text-[var(--fg-subtle)]">
                Session assurance: {String((aal as Record<string, unknown>).current_level || "aal1")}
                {(aal as Record<string, unknown>).next_level
                  ? ` → ${String((aal as Record<string, unknown>).next_level)}`
                  : ""}
              </p>
            ) : null}

            {enabled && !enroll ? (
              <div className="space-y-3 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] p-4">
                <p className="text-sm text-[var(--fg)]">
                  Authenticator app is active on this account.
                </p>
                <div className="flex flex-wrap gap-2">
                  {verified.map((factor) => {
                    const id = factorIdOf(factor);
                    return (
                      <Button
                        key={id}
                        variant="secondary"
                        size="sm"
                        disabled={busy || !id}
                        onClick={() => void disable(id)}
                      >
                        Disable factor
                      </Button>
                    );
                  })}
                  <Button variant="ghost" size="sm" disabled={busy} onClick={() => void regenerate()}>
                    Regenerate recovery codes
                  </Button>
                </div>
              </div>
            ) : null}

            {!enabled && !enroll ? (
              <Button
                disabled={startEnroll.isPending}
                onClick={() => startEnroll.mutate()}
              >
                {startEnroll.isPending ? "Preparing…" : "Enable two-factor authentication"}
              </Button>
            ) : null}

            {enroll ? (
              <div className="space-y-4 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] p-4">
                <p className="text-sm text-[var(--fg)]">
                  Scan this QR code with your authenticator app, then enter the six-digit code.
                </p>
                {enroll.qr_code ? (
                  enroll.qr_code.includes("<svg") ? (
                    <div
                      className="mx-auto w-fit rounded-lg bg-white p-3"
                      dangerouslySetInnerHTML={{ __html: enroll.qr_code }}
                    />
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={enroll.qr_code}
                      alt="Authenticator QR code"
                      className="mx-auto h-40 w-40 rounded-lg bg-white p-2"
                    />
                  )
                ) : null}
                {enroll.secret ? (
                  <div className="space-y-1">
                    <Label>Manual setup key</Label>
                    <code className="block break-all rounded bg-[var(--bg)] px-3 py-2 font-mono text-xs">
                      {enroll.secret}
                    </code>
                  </div>
                ) : null}
                <div className="space-y-1.5">
                  <Label htmlFor="mfa-enroll-code">Authenticator code</Label>
                  <Input
                    id="mfa-enroll-code"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    value={verifyCode}
                    onChange={(e) =>
                      setVerifyCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                    }
                    placeholder="000000"
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    disabled={busy || !/^\d{6}$/.test(verifyCode)}
                    onClick={() => void confirmEnroll()}
                  >
                    {busy ? "Verifying…" : "Confirm and enable"}
                  </Button>
                  <Button
                    variant="ghost"
                    disabled={busy}
                    onClick={() => {
                      setEnroll(null);
                      setVerifyCode("");
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : null}

            {recoveryCodes && recoveryCodes.length > 0 ? (
              <div
                className={cn(
                  "space-y-2 rounded-[var(--radius-os)] border border-[var(--accent)]/30",
                  "bg-[var(--accent-soft)]/20 p-4",
                )}
              >
                <p className="text-sm font-medium text-[var(--fg)]">
                  Save these recovery codes now. They are shown once.
                </p>
                <ul className="grid gap-1 sm:grid-cols-2">
                  {recoveryCodes.map((code) => (
                    <li key={code} className="font-mono text-sm tracking-wide">
                      {code}
                    </li>
                  ))}
                </ul>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    void navigator.clipboard.writeText(recoveryCodes.join("\n"));
                    toast.success("Recovery codes copied");
                  }}
                >
                  Copy codes
                </Button>
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
