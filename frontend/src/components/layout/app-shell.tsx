"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { CommandPalette } from "@/components/layout/command-palette";
import { MobileTabBar } from "@/components/layout/mobile-tab-bar";
import { useAuth } from "@/providers/auth-provider";
import { Skeleton } from "@/components/ui/skeleton";
import { OfflineBanner } from "@/components/system/offline-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { cn } from "@/lib/utils";
import { labelForHref, pushRecentPage } from "@/lib/workspace/nav-memory";
import { primaryRail } from "@/components/layout/nav-config";

/** Full-bleed zero-scroll operating surfaces. */
const OS_FULLBLEED_PATHS = [
  "/terminal",
  "/workspace",
  "/execution",
  "/portfolio",
  "/research",
  "/ai-signals",
];

function deskId(pathname: string): string {
  if (
    pathname.startsWith("/terminal") ||
    pathname.startsWith("/workspace") ||
    pathname.startsWith("/execution")
  ) {
    return "terminal";
  }
  if (
    pathname.startsWith("/portfolio") ||
    pathname.startsWith("/performance") ||
    pathname.startsWith("/exposure") ||
    pathname.startsWith("/allocation") ||
    pathname.startsWith("/book") ||
    pathname.startsWith("/risk-center")
  ) {
    return "book";
  }
  if (pathname.startsWith("/research") || pathname.startsWith("/screeners")) {
    return "research";
  }
  if (pathname.startsWith("/ai-signals") || pathname.startsWith("/counsel")) {
    return "counsel";
  }
  if (pathname.startsWith("/journal") || pathname.startsWith("/trade-replay")) {
    return "journal";
  }
  if (pathname.startsWith("/broker") || pathname.startsWith("/gateway")) {
    return "broker";
  }
  if (pathname.startsWith("/notifications") || pathname.startsWith("/alerts")) {
    return "inbox";
  }
  if (pathname.startsWith("/settings") || pathname.startsWith("/integrations")) {
    return "settings";
  }
  return "app";
}

/** ⌘1–8 map to desks that declare a shortcut (not raw rail order). */
const DESK_SHORTCUTS: string[] = (() => {
  const slots: string[] = [];
  for (const item of primaryRail) {
    if (!item.shortcut) continue;
    const idx = Number(item.shortcut) - 1;
    if (idx >= 0 && idx <= 7) slots[idx] = item.href;
  }
  return slots;
})();

export function AppShell({ children }: { children: React.ReactNode }) {
  const { loading, isAuthenticated } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [cmdOpen, setCmdOpen] = useState(false);
  const isFullBleed = OS_FULLBLEED_PATHS.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );
  const isTerminal = deskId(pathname) === "terminal";
  const compactChrome = isTerminal || isFullBleed;

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  useEffect(() => {
    if (!pathname || pathname.startsWith("/login")) return;
    pushRecentPage({ href: pathname, label: labelForHref(pathname) });
  }, [pathname]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) return;
      if (e.key < "1" || e.key > "8") return;
      const idx = Number(e.key) - 1;
      const href = DESK_SHORTCUTS[idx];
      if (!href) return;
      e.preventDefault();
      router.push(href);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bg)]">
        <div className="w-full max-w-sm space-y-3 p-6">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="flex min-h-screen flex-col bg-[var(--bg)] text-[var(--fg)]">
      <OfflineBanner />
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar onOpenCommand={() => setCmdOpen(true)} compact={compactChrome} />
          <main
            id="main-content"
            data-desk={deskId(pathname)}
            className={cn(
              "flex-1",
              isFullBleed
                ? "overflow-hidden p-0"
                : "overflow-x-clip overflow-y-auto p-4 sm:p-6 lg:p-8",
              "pb-[calc(4.25rem+env(safe-area-inset-bottom))] lg:pb-0",
            )}
            tabIndex={-1}
          >
            <ErrorBoundary>
              <div
                key={pathname}
                className={cn(
                  isFullBleed
                    ? "h-[calc(100dvh-3.25rem-4.25rem)] w-full max-w-none lg:h-[calc(100dvh-3.25rem)] qf-motion-desk"
                    : "mx-auto w-full max-w-[1600px] qf-motion-desk",
                )}
              >
                {children}
              </div>
            </ErrorBoundary>
          </main>
        </div>
      </div>
      <MobileTabBar />
      <CommandPalette open={cmdOpen} onOpenChange={setCmdOpen} />
    </div>
  );
}
