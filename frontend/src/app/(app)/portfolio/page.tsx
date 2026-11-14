"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { DeskSkeleton } from "@/components/desk/primitives";

/** Phase 3: Portfolio desk aliases Book OS. */
export default function PortfolioPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/book");
  }, [router]);
  return (
    <div className="flex h-full items-center justify-center p-6">
      <DeskSkeleton variant="page" />
    </div>
  );
}
