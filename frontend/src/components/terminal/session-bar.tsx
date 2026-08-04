"use client";

import { memo, useMemo } from "react";
import Link from "next/link";
import { Cable, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TerminalSymbolSwitcher } from "@/components/terminal/symbol-switcher";
import { useTradingSession } from "@/providers/trading-session-provider";
import { num, str } from "@/lib/desk";
import { cn, formatCurrency } from "@/lib/utils";
import type { RealtimeStatus } from "@/lib/realtime/types";

/**
 * One SessionBar for Terminal.
 * Account + connectivity only — no gateway HTTP diagnostics.
 */
export const TerminalSessionBar = memo(function TerminalSessionBar({
  symbol,
  onSymbolChange,
  bid,
  ask,
  realtime,
  className,
}: {
  symbol: string;
  onSymbolChange?: (code: string) => void;
  bid?: number;
  ask?: number;
  realtime?: RealtimeStatus;
  className?: string;
}) {
  const session = useTradingSession();
  const equity = num(session.equity);
  const free = num(session.freeMargin);
  const openPnl = useMemo(
    () => session.positions.reduce((s, p) => s + num(p.profit, 0), 0),
    [session.positions],
  );
  const spread =
    typeof bid === "number" &&
    typeof ask === "number" &&
    Number.isFinite(bid) &&
    Number.isFinite(ask)
      ? ask - bid
      : null;
  const latency =
    realtime?.latencyMs ??
    (Number.isFinite(num(session.latencyMs)) ? num(session.latencyMs) : null);

  return (
    <div
      className={cn(
        "flex h-8 shrink-0 items-center gap-2.5 border-b border-[var(--border)] bg-[var(--bg-elevated)] px-2",
        className,
      )}
      role="status"
      aria-live="polite"
      aria-label="Session"
    >
      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
        <Badge tone={session.connected ? "success" : session.gatewayOnline ? "warning" : "neutral"} className="shrink-0 h-5 px-1.5 text-[10px]">
          <span className="qf-status-dot mr-1 h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
          {session.connected
            ? "Broker live"
            : session.gatewayOnline
              ? "Gateway only"
              : "Broker off"}
        </Badge>
        <span className="truncate qf-caption tabular text-[var(--fg-muted)]">
          {str(session.server, "—")}
          <span className="text-[var(--fg-subtle)]"> · </span>
          {str(session.login, "—")}
        </span>
        {onSymbolChange ? (
          <TerminalSymbolSwitcher symbol={symbol} onSelect={onSymbolChange} />
        ) : (
          <span className="hidden truncate font-mono text-[11px] font-medium text-[var(--fg)] sm:inline">
            {symbol}
          </span>
        )}
        {spread != null ? (
          <span className="hidden tabular text-[10px] text-[var(--fg-subtle)] md:inline">
            spr {spread.toFixed(5)}
          </span>
        ) : null}
        {latency != null && Number.isFinite(latency) ? (
          <span className="hidden tabular text-[10px] text-[var(--fg-subtle)] lg:inline">
            {Math.round(latency)} ms
          </span>
        ) : null}
      </div>

      <dl className="hidden items-center gap-3.5 text-[11px] md:flex">
        <div className="flex items-baseline gap-1">
          <dt className="text-[10px] uppercase tracking-[0.06em] text-[var(--fg-subtle)]">Eq</dt>
          <dd className="tabular font-medium text-[var(--fg)]">
            {Number.isFinite(equity) ? formatCurrency(equity) : "—"}
          </dd>
        </div>
        <div className="flex items-baseline gap-1">
          <dt className="text-[10px] uppercase tracking-[0.06em] text-[var(--fg-subtle)]">Free</dt>
          <dd className="tabular font-medium text-[var(--fg)]">
            {Number.isFinite(free) ? formatCurrency(free) : "—"}
          </dd>
        </div>
        <div className="flex items-baseline gap-1">
          <dt className="text-[10px] uppercase tracking-[0.06em] text-[var(--fg-subtle)]">Float</dt>
          <dd
            className={cn(
              "tabular font-medium",
              openPnl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
            )}
          >
            {formatCurrency(openPnl)}
          </dd>
        </div>
        <div className="flex items-baseline gap-1">
          <dt className="text-[10px] uppercase tracking-[0.06em] text-[var(--fg-subtle)]">Pos</dt>
          <dd className="tabular font-medium text-[var(--fg)]">
            {session.positions.length}
          </dd>
        </div>
      </dl>

      <div className="flex shrink-0 items-center gap-0.5">
        <Button
          size="sm"
          variant="ghost"
          className="h-6 w-6 px-0"
          disabled={session.refreshing}
          onClick={() => void session.invalidateAll()}
          aria-label="Sync session"
        >
          <RefreshCw
            className={cn("h-3.5 w-3.5", session.refreshing && "animate-spin")}
          />
        </Button>
        <Button size="sm" variant="ghost" className="h-6 w-6 px-0" asChild>
          <Link href="/broker" aria-label="Open Broker">
            <Cable className="h-3.5 w-3.5" />
          </Link>
        </Button>
      </div>
    </div>
  );
});
