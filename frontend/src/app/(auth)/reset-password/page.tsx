"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { clearSession, saveSession, type AuthSession } from "@/lib/auth/session";
import { recordAudit } from "@/lib/observability/audit";

const schema = z
  .object({
    password: z.string().min(8, "At least 8 characters"),
    confirm: z.string().min(8),
  })
  .refine((v) => v.password === v.confirm, {
    message: "Passwords do not match",
    path: ["confirm"],
  });

type FormValues = z.infer<typeof schema>;

function parseHashParams(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const raw = window.location.hash.replace(/^#/, "");
  if (!raw) return {};
  const out: Record<string, string> = {};
  for (const part of raw.split("&")) {
    const [k, v] = part.split("=");
    if (k) out[decodeURIComponent(k)] = decodeURIComponent(v || "");
  }
  return out;
}

function ResetForm() {
  const params = useSearchParams();
  const router = useRouter();
  const [phase, setPhase] = useState<"boot" | "ready" | "expired" | "done">("boot");
  const [error, setError] = useState<string | null>(null);

  const queryToken = params.get("token_hash") || params.get("token") || "";
  const queryType = params.get("type") || "recovery";

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { password: "", confirm: "" },
  });

  const expiredHint = useMemo(
    () =>
      error ||
      "This reset link is invalid or has expired. Request a new link to continue.",
    [error],
  );

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const hash = parseHashParams();
        const hashType = hash.type || queryType;
        if (hashType && hashType !== "recovery" && hashType !== "email") {
          // Still allow recovery/email OTP types only for this page.
        }

        if (hash.access_token && hash.refresh_token) {
          const session: AuthSession = {
            access_token: hash.access_token,
            refresh_token: hash.refresh_token,
            expires_in: Number(hash.expires_in || 3600),
            token_type: hash.token_type || "bearer",
            user: {
              id: "",
              email: "",
              display_name: "",
              role: "user",
              status: "active",
            },
          };
          saveSession(session);
          try {
            const me = await authApi.me();
            saveSession({ ...session, user: me });
          } catch {
            /* password change still works with access token */
          }
          if (!cancelled) {
            window.history.replaceState(null, "", "/reset-password");
            setPhase("ready");
          }
          return;
        }

        if (queryToken) {
          const session = (await authApi.verifyEmail(
            queryToken,
            queryType || "recovery",
          )) as AuthSession;
          if ("access_token" in session) {
            saveSession(session);
            if (!cancelled) {
              setPhase("ready");
            }
            return;
          }
        }

        if (!cancelled) {
          setError("Missing or incomplete reset token.");
          setPhase("expired");
        }
      } catch (e) {
        clearSession();
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : "Reset link expired or invalid.");
          setPhase("expired");
          recordAudit("password_reset", "failure", "Reset token rejected");
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [queryToken, queryType]);

  if (phase === "boot") {
    return <p className="text-sm text-[var(--fg-muted)]">Validating reset link…</p>;
  }

  if (phase === "expired") {
    return (
      <div className="space-y-4">
        <p className="text-sm text-[var(--danger)]" role="alert">
          {expiredHint}
        </p>
        <Button className="w-full" asChild>
          <Link href="/forgot-password">Request a new reset link</Link>
        </Button>
      </div>
    );
  }

  if (phase === "done") {
    return (
      <div className="space-y-4">
        <p className="text-sm text-[var(--fg-muted)]">
          Password updated. You can sign in with your new credentials.
        </p>
        <Button className="w-full" onClick={() => router.replace("/login")}>
          Continue to sign in
        </Button>
      </div>
    );
  }

  return (
    <form
      className="space-y-4"
      onSubmit={form.handleSubmit(async (values) => {
        try {
          await authApi.changePassword(values.password);
          recordAudit("password_reset", "success", "Password reset completed");
          clearSession();
          toast.success("Password updated");
          setPhase("done");
        } catch (e) {
          recordAudit("password_reset", "failure", "Password reset completion failed");
          const msg = e instanceof ApiError ? e.message : "Unable to update password";
          if (/expired|invalid|token/i.test(msg)) {
            clearSession();
            setError(msg);
            setPhase("expired");
          } else {
            toast.error(msg);
          }
        }
      })}
    >
      <div className="space-y-2">
        <Label htmlFor="password">New password</Label>
        <Input
          id="password"
          type="password"
          autoComplete="new-password"
          {...form.register("password")}
        />
        {form.formState.errors.password ? (
          <p className="text-xs text-[var(--danger)]">{form.formState.errors.password.message}</p>
        ) : null}
      </div>
      <div className="space-y-2">
        <Label htmlFor="confirm">Confirm password</Label>
        <Input
          id="confirm"
          type="password"
          autoComplete="new-password"
          {...form.register("confirm")}
        />
        {form.formState.errors.confirm ? (
          <p className="text-xs text-[var(--danger)]">{form.formState.errors.confirm.message}</p>
        ) : null}
      </div>
      <Button className="w-full" type="submit" disabled={form.formState.isSubmitting}>
        Update password
      </Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <AuthShell
      title="Choose a new password"
      subtitle="Complete the reset from your email link. Links expire for security."
    >
      <Suspense fallback={<p className="text-sm text-[var(--fg-muted)]">Loading…</p>}>
        <ResetForm />
      </Suspense>
      <p className="mt-4 text-center text-sm text-[var(--fg-muted)]">
        <Link href="/login" className="text-[var(--accent)]">
          Back to sign in
        </Link>
      </p>
    </AuthShell>
  );
}
