"use client";

import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { tradingSessionApi } from "@/lib/api/endpoints";
import { asRecord, str } from "@/lib/desk";
import {
  connectionShortLabel,
  resolveConnectionPresentation,
  TRADER_POLL_MS,
  type ConnectionPresentation,
} from "@/lib/trading/trader-ux";
import { cn, formatRelativeTime } from "@/lib/utils";

function lastVerifiedLabel(iso: string | null): string {
  if (!iso) return "—";
  const relative = formatRelativeTime(iso);
  return relative || iso.replace("T", " ").slice(0, 19);
}

export function ConnectionStatus({
  session: sessionOverride,
  connecting = false,
  compact = false,
  className,
}: {
  session?: Record<string, unknown>;
  connecting?: boolean;
  compact?: boolean;
  className?: string;
}) {
  const sessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    retry: false,
    refetchInterval: TRADER_POLL_MS,
    enabled: sessionOverride == null,
  });
  const session = sessionOverride ?? asRecord(sessionQ.data);
  const view: ConnectionPresentation = resolveConnectionPresentation(session, {
    connecting,
  });

  if (compact) {
    return (
      <Badge
        tone={view.tone}
        className={cn("h-5 shrink-0 px-1.5 text-[10px]", className)}
        role="status"
        aria-live="polite"
        aria-label={`Connection ${connectionShortLabel(view.state)}`}
      >
        <span
          className="qf-status-dot mr-1 h-1.5 w-1.5 rounded-full bg-current"
          aria-hidden
        />
        {connectionShortLabel(view.state)}
      </Badge>
    );
  }

  return (
    <section
      className={cn(
        "grid min-w-0 gap-2 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] p-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6",
        className,
      )}
      role="status"
      aria-live="polite"
      aria-label="Broker connection status"
    >
      <StatusCell label="Connection">
        <Badge tone={view.tone}>{connectionShortLabel(view.state)}</Badge>
      </StatusCell>
      <StatusCell label="Health">{view.health}</StatusCell>
      <StatusCell label="Login">{view.maskedLogin}</StatusCell>
      <StatusCell label="Server">{view.server}</StatusCell>
      <StatusCell label="Last verified">
        {lastVerifiedLabel(view.lastVerified)}
      </StatusCell>
      <StatusCell label="Ownership">
        {view.ownership === "owned" ? "Owned" : "None"}
      </StatusCell>
    </section>
  );
}

function StatusCell({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
        {label}
      </p>
      <div className="mt-0.5 truncate text-sm font-medium text-[var(--fg)]">
        {typeof children === "string" ? str(children) : children}
      </div>
    </div>
  );
}
