"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { saveSession, type AuthSession } from "@/lib/auth/session";

function VerifyForm() {
  const params = useSearchParams();
  const router = useRouter();
  const [token, setToken] = useState(params.get("token_hash") || "");
  const type = params.get("type") || "email";

  return (
    <form
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          const result = await authApi.verifyEmail(token, type);
          if (result && typeof result === "object" && "access_token" in result) {
            saveSession(result as AuthSession);
            toast.success("Email verified");
            router.replace("/terminal");
            return;
          }
          toast.success("Email verified — sign in to continue");
          router.replace("/login");
        } catch (err) {
          toast.error(err instanceof ApiError ? err.message : "Verification failed");
        }
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="token">Verification token</Label>
        <Input id="token" value={token} onChange={(e) => setToken(e.target.value)} />
      </div>
      <Button className="w-full" type="submit">
        Verify email
      </Button>
    </form>
  );
}

export default function VerifyEmailPage() {
  return (
    <AuthShell
      title="Verify email"
      subtitle="Paste the token from your verification email, or open the link we sent."
    >
      <Suspense fallback={<p className="text-sm text-[var(--fg-muted)]">Loading…</p>}>
        <VerifyForm />
      </Suspense>
      <p className="mt-4 text-center text-sm text-[var(--fg-muted)]">
        <Link href="/login" className="text-[var(--accent)]">
          Continue to sign in
        </Link>
      </p>
    </AuthShell>
  );
}
