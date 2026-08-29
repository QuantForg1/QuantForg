"use client";

import { memo, useMemo } from "react";
import Link from "next/link";
import { Cable, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TerminalSymbolSwitcher } from "@/components/terminal/symbol-switcher";
import { ConnectionStatus } from "@/components/trading/connection-status";
import { useTradingSession } from "@/providers/trading-session-provider";
import { num, str } from "@/lib/desk";
import {
  isAutonomousTerminalMode,
  type TerminalMode,
} from "@/lib/terminal/autonomous-focus";
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
  terminalMode = "MANUAL",
  className,
}: {
  symbol: string;
  onSymbolChange?: (code: string) => void;
  bid?: number;
  ask?: number;
  realtime?: RealtimeStatus;
  terminalMode?: TerminalMode;
  className?: string;
}) {
  const session = useTradingSession();
  const equity = num(session.equity);
  const free = num(session.freeMargin);
  const openPnl = useMemo(() => {
    const values = session.positions.map((p) => num(p.profit));
    const finite = values.filter((n) => Number.isFinite(n));
    return finite.length > 0 ? finite.reduce((s, n) => s + n, 0) : Number.NaN;
  }, [session.positions]);
  const spread =
    typeof bid === "number" &&
    typeof ask === "number" &&
    Number.isFinite(bid) &&
    Number.isFinite(ask)
      ? ask - bid
      : null;

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
        <ConnectionStatus compact />
        <span className="truncate qf-caption tabular text-[var(--fg-muted)]">
          {str(session.server, "—")}
          <span className="text-[var(--fg-subtle)]"> · </span>
          {(() => {
            const raw = str(session.login, "");
            const digits = raw.replace(/\D/g, "") || raw.trim();
            if (!digits) return "—";
            if (digits.length <= 4) return "••••";
            return `${digits.slice(0, 2)}•••${digits.slice(-2)}`;
          })()}
        </span>
        {onSymbolChange ? (
          <TerminalSymbolSwitcher symbol={symbol} onSelect={onSymbolChange} />
        ) : (
          <span className="hidden truncate font-mono text-[11px] font-medium text-[var(--fg)] sm:inline">
            {symbol}
          </span>
        )}
        {isAutonomousTerminalMode(terminalMode) ? (
          <Badge
            tone="accent"
            className="hidden h-5 shrink-0 px-1.5 text-[10px] sm:inline-flex"
          >
            {terminalMode === "AUTONOMOUS_POSITION_OPEN" ? "Position" : "Auto"}
          </Badge>
        ) : null}
        {spread != null ? (
          <span className="hidden tabular text-[10px] text-[var(--fg-subtle)] md:inline">
            spr {spread.toFixed(5)}
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
              Number.isFinite(openPnl)
                ? openPnl >= 0
                  ? "text-[var(--success)]"
                  : "text-[var(--danger)]"
                : "text-[var(--fg)]",
            )}
          >
            {Number.isFinite(openPnl) ? formatCurrency(openPnl) : "—"}
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
