"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
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
import { saveSession, type AuthSession } from "@/lib/auth/session";

const schema = z
  .object({
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm: z.string().min(1, "Confirm your password"),
  })
  .refine((values) => values.password === values.confirm, {
    path: ["confirm"],
    message: "Passwords do not match",
  });

type FormValues = z.infer<typeof schema>;

async function hydrateRecoverySession(tokenHash: string | null, type: string) {
  if (tokenHash) {
    const result = await authApi.verifyEmail(tokenHash, type || "recovery");
    if (result && typeof result === "object" && "access_token" in result) {
      saveSession(result as AuthSession);
      return true;
    }
  }
  if (typeof window === "undefined") return false;
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const access = hash.get("access_token");
  const refresh = hash.get("refresh_token");
  if (!access) return false;
  window.sessionStorage.setItem("qf_access_token", access);
  if (refresh) window.sessionStorage.setItem("qf_refresh_token", refresh);
  const user = await authApi.me();
  saveSession({
    access_token: access,
    refresh_token: refresh || "",
    expires_in: Number(hash.get("expires_in") || 3600),
    token_type: "bearer",
    user,
  });
  window.history.replaceState(null, "", "/reset-password");
  return true;
}

function ResetForm() {
  const params = useSearchParams();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const tokenHash = params.get("token_hash");
  const type = params.get("type") || "recovery";
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { password: "", confirm: "" },
  });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const ok = await hydrateRecoverySession(tokenHash, type);
        if (!cancelled) {
          setReady(ok);
          setBlocked(!ok);
        }
      } catch (err) {
        if (!cancelled) {
          setBlocked(true);
          toast.error(err instanceof ApiError ? err.message : "Reset link is invalid or expired");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tokenHash, type]);

  if (!ready && !blocked) {
    return <p className="text-sm text-[var(--fg-muted)]">Checking reset link…</p>;
  }

  if (blocked) {
    return (
      <div className="space-y-4">
        <p className="text-sm leading-relaxed text-[var(--fg-muted)]">
          Open the reset link from your email, or request a new one.
        </p>
        <Button className="w-full" asChild>
          <Link href="/forgot-password">Request a new reset link</Link>
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
          toast.success("Password updated");
          router.replace("/login");
        } catch (err) {
          toast.error(err instanceof ApiError ? err.message : "Could not update password");
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
          <p className="text-xs text-[var(--danger)]">
            {form.formState.errors.password.message}
          </p>
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
          <p className="text-xs text-[var(--danger)]">
            {form.formState.errors.confirm.message}
          </p>
        ) : null}
      </div>
      <Button className="w-full" type="submit" disabled={form.formState.isSubmitting}>
        {form.formState.isSubmitting ? "Updating…" : "Update password"}
      </Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <AuthShell
      title="Choose a new password"
      subtitle="Use the link from your email to securely update your password."
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
