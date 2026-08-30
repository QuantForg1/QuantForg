"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps } from "@/lib/auth/ite-ops-access";
import { DeskSkeleton } from "@/components/desk/primitives";

/**
 * Dedicated Admin Portal shell.
 * Trader rail never links here — operators open /admin directly.
 * Backend require_roles(OWNER|ADMIN) still enforces privileged APIs.
 */
export default function AdminPortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { user, loading, isAuthenticated } = useAuth();
  const allowed = canAccessIteOps(user);

  useEffect(() => {
    if (loading) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (!allowed) {
      router.replace("/dashboard");
    }
  }, [allowed, isAuthenticated, loading, router]);

  if (loading || !isAuthenticated || !allowed) {
    return <DeskSkeleton variant="page" />;
  }

  return (
    <div className="min-w-0 space-y-4">
      <header className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--fg-subtle)]">
          QuantForg · Operations
        </p>
        <p className="mt-1 text-sm text-[var(--fg)]">
          Admin Portal · role {String(user?.role || "").toUpperCase()}
        </p>
        <p className="mt-1 text-xs text-[var(--fg-muted)]">
          Internal operations only. Research stays advisory. Opening Admin does
          not enable live trading. Privileged APIs enforce OWNER/ADMIN
          server-side.
        </p>
      </header>
      {children}
    </div>
  );
}
