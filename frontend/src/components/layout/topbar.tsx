"use client";

import Link from "next/link";
import { Bell, Command, LogOut, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/auth-provider";
import { usePathname, useRouter } from "next/navigation";
import { MobileNav } from "@/components/layout/sidebar";
import { useRealtime } from "@/hooks/realtime";
import { RealtimeConnectionBadge } from "@/components/realtime/connection-badge";
import { isPrimaryActive, primaryRail } from "@/components/layout/nav-config";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn } from "@/lib/utils";

function workspaceLabel(pathname: string): string {
  const desk = primaryRail.find((item) => isPrimaryActive(pathname, item));
  return desk?.label ?? "Workspace";
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
  const realtime = useRealtime();
  const session = useTradingSession();
  const desk = workspaceLabel(pathname);
  const initials =
    user?.display_name
      ?.split(/\s+/)
      .map((p) => p[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "QF";

  return (
    <header
      className={cn(
        "sticky top-0 z-30 flex items-center gap-2 border-b border-[var(--border)] bg-[var(--bg)]/85 px-3 backdrop-blur-md sm:gap-3 sm:px-4",
        compact ? "h-[3.25rem]" : "h-14",
      )}
    >
      <div className="shrink-0 lg:hidden">
        <MobileNav />
      </div>

      <div className="hidden min-w-0 shrink-0 items-center gap-2 sm:flex">
        <span className="truncate text-[13px] font-semibold tracking-tight text-[var(--fg)]">
          {desk}
        </span>
        <span className="h-3 w-px bg-[var(--border)]" aria-hidden />
        <span
          className={cn(
            "qf-caption truncate tabular",
            session.connected
              ? "text-[var(--success)]"
              : session.gatewayOnline === true
                ? "text-[var(--warning)]"
                : "text-[var(--fg-subtle)]",
          )}
          title={
            session.connected
              ? "Broker session attached"
              : session.gatewayOnline === true
                ? "Gateway reachable — broker session not attached"
                : session.gatewayOnline == null
                  ? "Connectivity status unknown (API/auth)"
                  : "No live broker session"
          }
        >
          {session.connected
            ? "MT5"
            : session.gatewayOnline === true
              ? "Gateway"
              : session.gatewayOnline == null
                ? "Unknown"
                : "Broker off"}
        </span>
      </div>

      <button
        type="button"
        onClick={onOpenCommand}
        aria-label="Open command palette"
        className={cn(
          "mx-auto flex w-full max-w-lg flex-1 items-center gap-2 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface)] px-3 text-left text-sm text-[var(--fg-muted)] transition-[border-color,background-color,box-shadow] duration-[var(--duration-os)] ease-[var(--ease-os)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
          compact ? "h-8 py-0" : "h-9 py-2",
        )}
      >
        <Search className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="flex-1 truncate">Search or jump…</span>
        <kbd className="hidden items-center gap-1 rounded border border-[var(--border)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--fg-muted)] sm:inline-flex">
          <Command className="h-3 w-3" aria-hidden />K
        </kbd>
      </button>

      <div className="ml-auto flex shrink-0 items-center gap-1 sm:gap-1.5">
        <RealtimeConnectionBadge
          status={realtime}
          className="hidden transition-opacity duration-[var(--duration-os)] md:inline-flex"
        />
        <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
          <Link href="/notifications" aria-label="Inbox">
            <Bell className="h-4 w-4" />
          </Link>
        </Button>
        <div
          className="hidden h-8 w-8 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface-2)] text-[11px] font-semibold text-[var(--fg)] sm:flex"
          title={user?.email ?? user?.display_name ?? "Profile"}
          aria-hidden
        >
          {initials}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
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
