"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { consumeAuthHashSession } from "@/lib/auth/email-confirm-hash";

/**
 * Client bridge for Supabase confirmation emails that land on `/` (or another
 * page) with `#access_token=…&type=signup`. Completes session hydrate and
 * routes into the product.
 */
export function EmailConfirmHashBridge() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        if (typeof window === "undefined") return;
        if (!window.location.hash.includes("access_token")) return;
        setBusy(true);
        const result = await consumeAuthHashSession();
        if (cancelled) return;
        if (result.kind === "recovery") {
          router.replace(`/reset-password${window.location.hash}`);
          return;
        }
        if (result.kind === "signup") {
          toast.success("Email confirmed. You are signed in.");
          router.replace("/dashboard");
        }
      } catch {
        if (!cancelled) {
          toast.error(
            "Email was confirmed, but sign-in could not be completed. Please log in.",
          );
          router.replace("/login");
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (!busy) return null;
  return (
    <div
      className="fixed inset-x-0 top-0 z-[60] border-b border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-4 py-2 text-center text-sm text-[var(--fg-muted)]"
      role="status"
    >
      Confirming your email…
    </div>
  );
}
