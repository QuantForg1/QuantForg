"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps } from "@/lib/auth/ite-ops-access";
import { DeskSkeleton } from "@/components/desk/primitives";

/**
 * Admin portal gate — client redirect mirrors backend require_roles(OWNER|ADMIN).
 * Privileged APIs still enforce authorization server-side; this layout must not
 * render admin UI for unauthenticated or non-operator users.
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
      <p className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--fg-muted)]">
        Operator area · role {String(user?.role || "").toUpperCase()} · backend
        APIs enforce OWNER/ADMIN. Research stays advisory; live trading is not
        enabled by opening Admin.
      </p>
      {children}
    </div>
  );
}
