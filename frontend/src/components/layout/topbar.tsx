"use client";

import Link from "next/link";
import { Bell, Command, LogOut, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/auth-provider";
import { useRouter } from "next/navigation";
import { MobileNav } from "@/components/layout/sidebar";
import { useRealtime } from "@/hooks/realtime";
import { RealtimeConnectionBadge } from "@/components/realtime/connection-badge";
import { cn } from "@/lib/utils";

export function Topbar({
  onOpenCommand,
  compact = false,
}: {
  onOpenCommand: () => void;
  compact?: boolean;
}) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const realtime = useRealtime();

  return (
    <header
      className={cn(
        "sticky top-0 z-30 flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg)]/80 px-3 backdrop-blur-md sm:px-4",
        compact ? "h-[3.25rem]" : "h-14",
      )}
    >
      <div className="mr-2 lg:hidden">
        <MobileNav />
      </div>
      <button
        type="button"
        onClick={onOpenCommand}
        aria-label="Open command palette"
        className={cn(
          "flex w-full max-w-md items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-left text-sm text-[var(--fg-muted)] transition-[border-color,background-color] duration-[var(--duration-os)] ease-[var(--ease-os)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)] focus-visible:outline-none",
          compact ? "h-8 py-0" : "h-9 py-2",
        )}
      >
        <Search className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="flex-1 truncate">Search pages, symbols, actions…</span>
        <kbd className="hidden items-center gap-1 rounded border border-[var(--border)] px-1.5 py-0.5 text-[10px] text-[var(--fg-muted)] sm:inline-flex">
          <Command className="h-3 w-3" aria-hidden />K
        </kbd>
      </button>
      <div className="ml-3 flex items-center gap-1.5">
        <RealtimeConnectionBadge
          status={realtime}
          className="hidden transition-opacity duration-[var(--duration-os)] md:inline-flex"
        />
        <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
          <Link href="/notifications" aria-label="Notifications">
            <Bell className="h-4 w-4" />
          </Link>
        </Button>
        {!compact ? (
          <div className="hidden text-right sm:block">
            <p className="text-sm font-medium text-[var(--fg)]">{user?.display_name}</p>
            <p className="text-xs text-[var(--fg-subtle)]">{user?.email}</p>
          </div>
        ) : null}
        <Button
          variant="secondary"
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
