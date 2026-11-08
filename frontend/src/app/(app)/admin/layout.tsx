"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps } from "@/lib/auth/ite-ops-access";
import { DeskSkeleton } from "@/components/desk/primitives";

/**
 * Admin route gate — chrome lives in AdminShell (app-shell).
 * Backend require_roles(OWNER|ADMIN) still enforces privileged APIs;
 * UI gate is verified platform owner via canAccessIteOps.
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

  return children;
}
