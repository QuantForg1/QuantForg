"use client";

import dynamic from "next/dynamic";
import { Suspense } from "react";
import { DeskSkeleton } from "@/components/desk/primitives";

const TerminalShell = dynamic(
  () => import("@/components/terminal/shell").then((m) => m.TerminalShell),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center p-6">
        <DeskSkeleton variant="page" />
      </div>
    ),
  },
);

/** Flagship Terminal OS — zero-scroll trading surface. */
export default function TerminalPage() {
  return (
    <div className="flex h-full min-h-0 w-full flex-col">
      <div className="min-h-0 flex-1">
        <Suspense
          fallback={
            <div className="flex h-full items-center justify-center p-6">
              <DeskSkeleton variant="page" />
            </div>
          }
        >
          <TerminalShell />
        </Suspense>
      </div>
    </div>
  );
}
