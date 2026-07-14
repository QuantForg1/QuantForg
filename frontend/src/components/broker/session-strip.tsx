"use client";

import { memo } from "react";
import Link from "next/link";
import { Cable, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn } from "@/lib/utils";

/** Compact session ribbon — single source of truth from TradingSessionProvider. */
export const SessionStrip = memo(function SessionStrip({
  className,
  showManage = true,
}: {
  className?: string;
  showManage?: boolean;
}) {
  const session = useTradingSession();

  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)]/90 px-4 py-3 sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={session.connected ? "success" : "warning"} className="gap-1.5">
          <span className="qf-status-dot h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
          {session.connected ? "Session live" : "Session offline"}
        </Badge>
        <Badge tone={session.gatewayOnline ? "accent" : "neutral"}>
          {session.gatewayLabel}
        </Badge>
        <span className="text-xs text-[var(--fg-subtle)]">
          {session.connected
            ? `${session.server} · login ${session.login}${
                session.latencyMs !== "—" ? ` · ${session.latencyMs} ms` : ""
              }`
            : "Open Broker Workspace to attach the live MT5 session"}
        </span>
      </div>
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="ghost"
          disabled={session.refreshing}
          onClick={() => void session.invalidateAll()}
          aria-label="Refresh trading session"
        >
          <RefreshCw
            className={cn("h-3.5 w-3.5", session.refreshing && "animate-spin")}
          />
          Sync
        </Button>
        {showManage ? (
          <Button size="sm" variant="secondary" asChild>
            <Link href="/broker">
              <Cable className="h-3.5 w-3.5" /> Broker Workspace
            </Link>
          </Button>
        ) : null}
      </div>
    </div>
  );
});
