"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps } from "@/lib/auth/ite-ops-access";
import { DeskSkeleton } from "@/components/desk/primitives";

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
    if (!isAuthenticated || !allowed) {
      router.replace("/dashboard");
    }
  }, [allowed, isAuthenticated, loading, router]);

  if (loading || !allowed) {
    return <DeskSkeleton variant="page" />;
  }

  return children;
}
