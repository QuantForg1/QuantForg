"use client";

import { useTradingSession } from "@/providers/trading-session-provider";
import { cn } from "@/lib/utils";

type Props = {
  className?: string;
  compact?: boolean;
};

/** Compact Railway ↔ Gateway ↔ MT5 status — reads TradingSession only (no duplicate poll). */
export function WeltradeGatewayStatus({ className, compact = false }: Props) {
  const session = useTradingSession();
  const online = session.gatewayOnline;
  const mt5 = session.connected;
  const label = session.gatewayLabel;
  const detail = session.gatewayDetail;
  const gatewayUrl = session.gatewayUrl;
  const latency = session.latencyMs;

  return (
    <div
      className={cn(
        "rounded-xl border border-[var(--border)] bg-[var(--surface)]/90 px-3 py-3",
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Broker Gateway
        </p>
        <span
          className={cn(
            "text-xs font-medium",
            online ? "text-[var(--success)]" : "text-[var(--fg)]",
          )}
        >
          {session.refreshing && !online ? "Checking…" : label}
        </span>
      </div>
      {!compact ? (
        <div className="mt-2 grid gap-1 text-[11px] text-[var(--fg-muted)] sm:grid-cols-2">
          <span>MT5: {mt5 ? "Connected" : "Not connected"}</span>
          <span>Latency: {latency !== "—" ? `${latency} ms` : "—"}</span>
          <span className="truncate">Login: {session.loginStatus}</span>
          <span className="truncate">Server: {session.server}</span>
        </div>
      ) : null}
      {!online && detail && detail !== "ok" ? (
        <p className="mt-2 break-words font-mono text-[11px] text-[var(--fg)]">
          {detail.slice(0, 240)}
        </p>
      ) : null}
      {gatewayUrl ? (
        <p className="mt-1 truncate text-[10px] text-[var(--fg-subtle)]">{gatewayUrl}</p>
      ) : null}
    </div>
  );
}
