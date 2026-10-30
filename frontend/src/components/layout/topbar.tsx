"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Bell, LogOut, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/auth-provider";
import { usePathname, useRouter } from "next/navigation";
import { MobileNav } from "@/components/layout/sidebar";
import { isPrimaryActive, primaryRail } from "@/components/layout/nav-config";
import { ConnectionStatus } from "@/components/trading/connection-status";
import { BrandLogo } from "@/components/brand/brand-logo";
import { cn, formatNumber } from "@/lib/utils";
import { mt5Api, platformApi } from "@/lib/api/endpoints";
import { asList, asRecord, num } from "@/lib/desk";
import { AUTONOMOUS_DISPLAY, TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { useTradingSession } from "@/providers/trading-session-provider";

function workspaceLabel(pathname: string): string {
  const desk = primaryRail.find((item) => isPrimaryActive(pathname, item));
  return desk?.label ?? "Workspace";
}

function sessionWindow(at: Date): string {
  const hour = at.getUTCHours();
  if (hour >= 7 && hour < 16) return "London";
  if (hour >= 16 && hour < 21) return "New York";
  if (hour >= 0 && hour < 7) return "Tokyo";
  return "Sydney";
}

function serverClock(raw: string): { label: string; at: Date } | null {
  if (!raw) return null;
  const asNum = Number(raw);
  const ms = Number.isFinite(asNum)
    ? asNum > 1e12
      ? asNum
      : asNum > 1e9
        ? asNum * 1000
        : NaN
    : Date.parse(raw);
  if (!Number.isFinite(ms)) return null;
  const at = new Date(ms);
  const label = at.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
  return { label: `${label} UTC`, at };
}

function MarketChrome() {
  const session = useTradingSession();
  const tickQ = useQuery({
    queryKey: ["shell-tick", TRADING_SYMBOL],
    queryFn: () => mt5Api.tick(TRADING_SYMBOL),
    enabled: session.connected,
    retry: false,
    staleTime: 10_000,
    refetchInterval: session.connected ? 15_000 : false,
  });
  const tick = asRecord(tickQ.data);
  const bid = num(tick.bid);
  const ask = num(tick.ask);
  const mid =
    Number.isFinite(bid) && Number.isFinite(ask)
      ? (bid + ask) / 2
      : Number.isFinite(bid)
        ? bid
        : NaN;
  const price = Number.isFinite(mid) ? formatNumber(mid, 2) : null;
  const rawTime = (value: unknown) =>
    value == null || value === "" ? "" : String(value);
  const clock = serverClock(rawTime(tick.time) || rawTime(tick.time_msc));
  const sessionAt = clock?.at ?? new Date();
  const sessionName = sessionWindow(sessionAt);
  const weekday = sessionAt.getUTCDay();
  const weekdaySession = weekday >= 1 && weekday <= 5;

  return (
    <div className="hidden min-w-0 items-center gap-3 lg:flex">
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {AUTONOMOUS_DISPLAY}
        </p>
        <p className="truncate text-sm font-semibold tabular text-[var(--fg)]">
          {price ?? (tickQ.isLoading && session.connected ? "Loading" : "—")}
        </p>
      </div>
      <span className="h-8 w-px bg-[var(--border)]" aria-hidden />
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Market session
        </p>
        <p className="flex items-center gap-1.5 text-sm font-medium text-[var(--fg)]">
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              weekdaySession ? "bg-[var(--success)]" : "bg-[var(--fg-subtle)]",
            )}
            aria-hidden
          />
          {sessionName}
        </p>
      </div>
      <span className="hidden h-8 w-px bg-[var(--border)] xl:block" aria-hidden />
      <div className="hidden xl:block">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Server time
        </p>
        <p className="text-sm font-medium text-[var(--fg)]">{clock?.label ?? "—"}</p>
      </div>
    </div>
  );
}

export function Topbar({
  onOpenCommand,
  compact = false,
}: {
  onOpenCommand: () => void;
  compact?: boolean;
}) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const desk = workspaceLabel(pathname);
  const initials =
    user?.display_name
      ?.split(/\s+/)
      .map((p) => p[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "QF";
  const unreadQ = useQuery({
    queryKey: ["shell-unread-notifications"],
    queryFn: () => platformApi.notifications(true),
    retry: false,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
  const unread = asList(unreadQ.data).length;

  return (
    <header
      className={cn(
        "z-30 flex items-center gap-2 border-b border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_92%,transparent)] px-3 backdrop-blur-md sm:gap-3 sm:px-4",
        compact ? "h-[3.25rem]" : "h-16",
      )}
    >
      <div className="shrink-0 lg:hidden">
        <MobileNav />
      </div>
      <Link href="/dashboard" className="hidden shrink-0 sm:block" aria-label="QuantForg overview">
        <BrandLogo size={28} caption="Institutional Trading Intelligence" />
      </Link>
      {!compact ? (
        <div className="hidden sm:block lg:hidden">
          <ConnectionStatus compact />
        </div>
      ) : null}

      <button
        type="button"
        onClick={onOpenCommand}
        aria-label="Open command palette"
        className={cn(
          "mx-auto flex w-full max-w-xl flex-1 items-center gap-2 rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_72%,transparent)] px-3 text-left text-sm text-[var(--fg-muted)] transition-[border-color,background-color,box-shadow] duration-[var(--duration-os)] ease-[var(--ease-os)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
          compact ? "h-8 py-0" : "h-10 py-2",
        )}
      >
        <Search className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="flex-1 truncate">
          <span className="sm:hidden">{desk}</span>
          <span className="hidden sm:inline">Search symbols, signals, strategies, or insights...</span>
        </span>
        <kbd className="hidden items-center rounded-md border border-[var(--border)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--fg-muted)] sm:inline-flex">
          Ctrl K
        </kbd>
      </button>

      <MarketChrome />

      <div className="ml-auto flex shrink-0 items-center gap-1 sm:gap-1.5">
        <div className="hidden md:block">
          <ConnectionStatus compact />
        </div>
        <Button variant="ghost" size="icon" className="relative h-9 w-9" asChild>
          <Link href="/notifications" aria-label={unread > 0 ? `Inbox, ${unread} unread` : "Inbox"}>
            <Bell className="h-4 w-4" />
            {unread > 0 ? (
              <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--danger)] px-1 text-[10px] font-semibold text-white">
                {unread > 9 ? "9+" : unread}
              </span>
            ) : null}
          </Link>
        </Button>
        <Button variant="ghost" size="icon" className="h-9 w-9" asChild>
          <Link href="/settings" aria-label="Profile and settings">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--accent)] text-[11px] font-semibold text-white">
              {initials}
            </span>
          </Link>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9"
          aria-label="Sign out"
          onClick={async () => {
            try {
              await logout();
            } catch {
              /* session cleared server-side or offline — still leave the desk */
            }
            router.replace("/login");
          }}
        >
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
