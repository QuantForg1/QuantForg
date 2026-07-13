"use client";

import Link from "next/link";
import { Bell, Command, LogOut, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/auth-provider";
import { useRouter } from "next/navigation";
import { MobileNav } from "@/components/layout/sidebar";
import { useRealtime } from "@/hooks/realtime";
import { RealtimeConnectionBadge } from "@/components/realtime/connection-badge";

export function Topbar({ onOpenCommand }: { onOpenCommand: () => void }) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const realtime = useRealtime();

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-[var(--border)] bg-[var(--bg)]/70 px-4 backdrop-blur-xl sm:px-6">
      <div className="mr-2 lg:hidden">
        <MobileNav />
      </div>
      <button
        type="button"
        onClick={onOpenCommand}
        aria-label="Open command palette"
        className="flex w-full max-w-md items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-left text-sm text-[var(--fg-muted)] transition hover:border-[var(--accent)]/40"
      >
        <Search className="h-4 w-4 shrink-0" />
        <span className="flex-1 truncate">Search markets, pages, actions…</span>
        <kbd className="hidden items-center gap-1 rounded border border-[var(--border)] px-1.5 py-0.5 text-[10px] text-[var(--fg-muted)] sm:inline-flex">
          <Command className="h-3 w-3" />K
        </kbd>
      </button>
      <div className="ml-4 flex items-center gap-2">
        <RealtimeConnectionBadge status={realtime} className="hidden md:inline-flex" />
        <Button variant="ghost" size="icon" asChild>
          <Link href="/notifications" aria-label="Notifications">
            <Bell className="h-4 w-4" />
          </Link>
        </Button>
        <div className="hidden text-right sm:block">
          <p className="text-sm font-medium text-[var(--fg)]">{user?.display_name}</p>
          <p className="text-xs text-[var(--fg-subtle)]">{user?.email}</p>
        </div>
        <Button
          variant="secondary"
          size="icon"
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
