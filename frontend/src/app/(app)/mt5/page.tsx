"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { DeskSkeleton } from "@/components/desk/primitives";

/** Legacy MT5 Accounts page — redirects to Broker Workspace. */
export default function Mt5RedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/broker");
  }, [router]);
  return <DeskSkeleton variant="page" />;
}
