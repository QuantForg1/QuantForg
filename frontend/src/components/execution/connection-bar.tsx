"use client";

import { memo, useMemo } from "react";
import Link from "next/link";
import { Cable, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RealtimeConnectionBadge } from "@/components/realtime/connection-badge";
import { useTradingSession } from "@/providers/trading-session-provider";
import { str } from "@/lib/desk";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { RealtimeStatus } from "@/lib/realtime/types";

function parseLatencyMs(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const n = Number.parseFloat(value.replace(/[^\d.]/g, ""));
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function latencyTone(ms: number | null): "success" | "warning" | "danger" | "neutral" {
  if (ms == null) return "neutral";
  if (ms < 80) return "success";
  if (ms < 200) return "warning";
  return "danger";
}

/**
 * Institutional desk status bar — single source of truth for session,
 * gateway readiness, and latency. Prefer `compact` inside the trading terminal.
 */
export const ConnectionBar = memo(function ConnectionBar({
  connected: connectedProp,
  server,
  login,
  latencyMs,
  tradingEnabled,
  realtime,
  compact = false,
  className,
}: {
  connected?: boolean;
  server?: unknown;
  login?: unknown;
  latencyMs?: unknown;
  tradingEnabled?: boolean;
  realtime?: RealtimeStatus;
  /** Slim single-row terminal chrome (no card padding). */
  compact?: boolean;
  className?: string;
}) {
  const session = useTradingSession();
  const connected = connectedProp ?? session.connected;
  const enabled = tradingEnabled ?? connected;

  const resolvedLatency = useMemo(() => {
    const fromProp = parseLatencyMs(latencyMs);
    if (fromProp != null) return fromProp;
    const fromRealtime = realtime?.latencyMs ?? null;
    if (fromRealtime != null && Number.isFinite(fromRealtime)) return fromRealtime;
    return parseLatencyMs(session.latencyMs);
  }, [latencyMs, realtime?.latencyMs, session.latencyMs]);

  const tone = latencyTone(resolvedLatency);
  const serverLabel = str(server ?? session.server, "MT5");
  const loginLabel = str(login ?? session.login, "—");

  const metaTitle = realtime
    ? [
        realtime.isLeader ? "Leader tab" : "Follower tab",
        realtime.visible ? "Visible" : "Background",
        realtime.updatedAt
          ? `Updated ${formatRelativeTime(new Date(realtime.updatedAt).toISOString())}`
          : null,
        realtime.lastError || null,
      ]
        .filter(Boolean)
        .join(" · ")
    : undefined;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5",
        compact
          ? "border-b border-[var(--border)] bg-[var(--surface)]/80 px-3 py-1.5"
          : "rounded-xl border border-[var(--border)] bg-[var(--surface)]/90 px-4 py-3",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <div className="flex min-w-0 flex-wrap items-center gap-1.5">
        <Badge tone={connected ? "success" : "warning"} className="gap-1.5">
          <span className="qf-status-dot h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
          {connected ? "Connected" : "Offline"}
        </Badge>
        <Badge tone={session.gatewayOnline || enabled ? "accent" : "neutral"}>
          {session.gatewayOnline ? session.gatewayLabel : enabled ? "Gateway ready" : "Send gated"}
        </Badge>
        {realtime ? (
          <span title={metaTitle}>
            <RealtimeConnectionBadge status={realtime} />
          </span>
        ) : null}
        {connected ? (
          <>
            <span className="hidden text-[11px] text-[var(--fg-subtle)] sm:inline" aria-hidden>
              ·
            </span>
            <span className="truncate text-[11px] tabular text-[var(--fg-muted)]">
              {serverLabel}
              <span className="text-[var(--fg-subtle)]"> · </span>
              login {loginLabel}
            </span>
            {resolvedLatency != null ? (
              <Badge tone={tone} className="tabular" title="Round-trip latency">
                {Math.round(resolvedLatency)} ms
              </Badge>
            ) : null}
          </>
        ) : (
          <span className="text-[11px] text-[var(--fg-subtle)]">
            Attach MT5 in Broker Workspace before live orders
          </span>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-1.5">
        <span className="mr-1 hidden text-[10px] uppercase tracking-wider text-[var(--fg-subtle)] lg:inline">
          B buy · S sell
        </span>
        <Button
          size="sm"
          variant="ghost"
          className={cn(compact && "h-7 px-2")}
          disabled={session.refreshing}
          onClick={() => void session.invalidateAll()}
          aria-label="Refresh trading session"
        >
          <RefreshCw
            className={cn("h-3.5 w-3.5", session.refreshing && "animate-spin")}
          />
          Sync
        </Button>
        <Button
          size="sm"
          variant="secondary"
          className={cn(compact && "h-7 px-2")}
          asChild
        >
          <Link href="/broker">
            <Cable className="h-3.5 w-3.5" />
            Broker
          </Link>
        </Button>
      </div>
    </div>
  );
});
