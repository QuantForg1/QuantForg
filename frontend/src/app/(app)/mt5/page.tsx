"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { DeskSkeleton } from "@/components/desk/primitives";

/** Legacy MT5 Accounts page — redirected to unified Broker Connection. */
export default function Mt5RedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/broker");
  }, [router]);
  return <DeskSkeleton rows={4} />;
}
