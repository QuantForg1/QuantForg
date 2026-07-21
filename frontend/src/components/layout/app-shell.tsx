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
    pathname.startsWith("/book")
  ) {
    return "portfolio";
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
  if (pathname.startsWith("/monitoring") || pathname.startsWith("/ops")) {
    return "operations";
  }
  if (pathname.startsWith("/notifications") || pathname.startsWith("/alerts")) {
    return "inbox";
  }
  if (pathname.startsWith("/settings")) return "settings";
  return "app";
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { loading, isAuthenticated } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [cmdOpen, setCmdOpen] = useState(false);
  const isFullBleed = OS_FULLBLEED_PATHS.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );
  const isTerminal = deskId(pathname) === "terminal";

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/login");
  }, [loading, isAuthenticated, router]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) return;
      if (e.key === "1") {
        e.preventDefault();
        router.push("/terminal");
      } else if (e.key === "2") {
        e.preventDefault();
        router.push("/portfolio");
      } else if (e.key === "3") {
        e.preventDefault();
        router.push("/research");
      } else if (e.key === "4") {
        e.preventDefault();
        router.push("/journal");
      } else if (e.key === "5") {
        e.preventDefault();
        router.push("/broker");
      } else if (e.key === "6") {
        e.preventDefault();
        router.push("/monitoring");
      }
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
          <Topbar onOpenCommand={() => setCmdOpen(true)} />
          <main
            id="main-content"
            data-desk={deskId(pathname)}
            className={cn(
              "flex-1",
              isFullBleed
                ? "overflow-hidden p-0"
                : "overflow-x-clip overflow-y-auto p-4 sm:p-6 lg:p-8",
              // Reserve space for mobile tab bar
              "pb-[calc(4.25rem+env(safe-area-inset-bottom))] lg:pb-0",
              isTerminal && "lg:pb-0",
            )}
            tabIndex={-1}
          >
            <ErrorBoundary>
              <div
                className={cn(
                  "qf-fade-in",
                  isFullBleed
                    ? "h-[calc(100dvh-4rem-4.25rem)] w-full max-w-none lg:h-[calc(100dvh-4rem)]"
                    : "mx-auto w-full max-w-[1600px]",
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
