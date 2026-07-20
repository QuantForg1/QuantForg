"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { CommandPalette } from "@/components/layout/command-palette";
import { useAuth } from "@/providers/auth-provider";
import { Skeleton } from "@/components/ui/skeleton";
import { OfflineBanner } from "@/components/system/offline-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { cn } from "@/lib/utils";

const TERMINAL_PATHS = ["/terminal", "/workspace", "/execution"];
const OS_FULLBLEED_PATHS = [...TERMINAL_PATHS, "/book", "/research", "/counsel"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { loading, isAuthenticated } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [cmdOpen, setCmdOpen] = useState(false);
  const isFullBleed = OS_FULLBLEED_PATHS.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );

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
        router.push("/book");
      } else if (e.key === "3") {
        e.preventDefault();
        router.push("/research");
      } else if (e.key === "4") {
        e.preventDefault();
        router.push("/counsel");
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
            data-desk={
              pathname.startsWith("/terminal") ||
              pathname.startsWith("/workspace") ||
              pathname.startsWith("/execution")
                ? "terminal"
                : pathname.startsWith("/book")
                  ? "book"
                  : pathname.startsWith("/research")
                    ? "research"
                    : pathname.startsWith("/counsel")
                      ? "counsel"
                      : pathname.startsWith("/journal")
                        ? "journal"
                        : pathname.startsWith("/broker")
                          ? "broker"
                          : pathname.startsWith("/inbox")
                            ? "inbox"
                            : pathname.startsWith("/settings")
                              ? "settings"
                              : "app"
            }
            className={cn(
              "flex-1",
              isFullBleed
                ? "overflow-hidden p-0"
                : "overflow-x-clip overflow-y-auto p-4 sm:p-6 lg:p-8",
            )}
            tabIndex={-1}
          >
            <ErrorBoundary>
              <div
                className={cn(
                  "qf-fade-in",
                  isFullBleed
                    ? "h-[calc(100dvh-4rem)] w-full max-w-none"
                    : "mx-auto w-full max-w-[1600px]",
                )}
              >
                {children}
              </div>
            </ErrorBoundary>
          </main>
        </div>
      </div>
      <CommandPalette open={cmdOpen} onOpenChange={setCmdOpen} />
    </div>
  );
}
