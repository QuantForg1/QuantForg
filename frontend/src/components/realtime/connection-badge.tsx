"use client";

import { memo } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { RealtimeStatus } from "@/lib/realtime/types";
import { formatRelativeTime } from "@/lib/utils";

export const RealtimeConnectionBadge = memo(function RealtimeConnectionBadge({
  status,
  className,
}: {
  status: RealtimeStatus;
  className?: string;
}) {
  const tone = !status.online
    ? "danger"
    : status.transport === "polling"
      ? "success"
      : status.transport === "websocket"
        ? "accent"
        : "warning";

  const label = !status.online
    ? "Offline"
    : "Live";

  return (
    <Badge tone={tone} className={cn("gap-1.5", className)}>
      <span className="qf-status-dot h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {label}
    </Badge>
  );
});

export const RealtimeMeta = memo(function RealtimeMeta({
  status,
  className,
}: {
  status: RealtimeStatus;
  className?: string;
}) {
  return (
    <p className={cn("text-[11px] text-[var(--fg-subtle)]", className)} aria-live="polite">
      {status.isLeader ? "Leader tab" : "Follower tab"}
      {" · "}
      {status.visible ? "Visible" : "Background"}
      {status.updatedAt
        ? ` · Updated ${formatRelativeTime(new Date(status.updatedAt).toISOString())}`
        : null}
      {status.lastError ? ` · ${status.lastError}` : null}
    </p>
  );
});
