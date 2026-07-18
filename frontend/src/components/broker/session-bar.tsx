"use client";

import { cn } from "@/lib/utils";
import { SessionStrip } from "@/components/broker/session-strip";

/**
 * SessionBar — single session status surface for desks outside Terminal.
 * Do not stack gateway HTTP diagnostics here; those belong in Settings/admin.
 */
export function SessionBar({ className }: { className?: string }) {
  return (
    <div className={cn("qf-session-bar", className)} role="status" aria-live="polite">
      <SessionStrip />
    </div>
  );
}
