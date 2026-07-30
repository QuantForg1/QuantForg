"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { DeskSkeleton } from "@/components/desk/primitives";

/** Alias route → canonical NOC Command Center. */
export default function AdminOperationsRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/admin/noc");
  }, [router]);
  return <DeskSkeleton rows={6} />;
}
