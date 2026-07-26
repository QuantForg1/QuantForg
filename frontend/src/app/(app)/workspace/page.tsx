"use client";

import dynamic from "next/dynamic";
import { Suspense } from "react";
import { DeskSkeleton } from "@/components/desk/primitives";

/**
 * Legacy /workspace path — same Terminal OS as /terminal.
 * next.config also redirects here → /terminal; this keeps deep links consistent.
 */
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

export default function WorkspacePage() {
  return (
    <div className="h-full min-h-0 w-full">
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
  );
}
