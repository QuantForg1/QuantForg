"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ArrowLeft, LogOut, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { BrandLogo } from "@/components/brand/brand-logo";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/auth-provider";
import { OfflineBanner } from "@/components/system/offline-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  ADMIN_NAV_GROUPS,
  ADMIN_SIDEBAR_WIDTH,
  adminNavActive,
} from "@/components/admin/admin-nav-config";

function useLocationHash(): string {
  const [hash, setHash] = useState("");
  useEffect(() => {
    const sync = () => setHash(window.location.hash);
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);
  return hash;
}

function AdminNavBody({
  onNavigate,
  className,
}: {
  onNavigate?: () => void;
  className?: string;
}) {
  const pathname = usePathname();
  const hash = useLocationHash();

  return (
    <nav
      className={cn("flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-3", className)}
      aria-label="Admin Portal navigation"
    >
      {ADMIN_NAV_GROUPS.map((group) => (
        <div key={group.title}>
          <p className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            {group.title}
          </p>
          <ul className="space-y-0.5">
            {group.items.map((item) => {
              const active = adminNavActive(pathname, hash, item.href);
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    title={item.hint}
                    className={cn(
                      "flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-colors",
                      active
                        ? "bg-[var(--accent)] text-white shadow-[inset_3px_0_0_0_rgba(255,255,255,0.85)]"
                        : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden />
                    <span className="min-w-0 flex-1 truncate">{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function AdminMobileNav() {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(() => closeRef.current?.focus(), 0);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="lg:hidden">
      <Button
        variant="secondary"
        size="icon"
        aria-label={open ? "Close admin menu" : "Open admin menu"}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
      </Button>
      {open ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-[color-mix(in_srgb,var(--bg)_50%,#000)]"
            aria-label="Dismiss menu"
            onClick={() => setOpen(false)}
          />
          <aside
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="absolute inset-y-0 left-0 flex w-[min(20rem,88vw)] flex-col border-r border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_88%,transparent)] shadow-[var(--shadow-elevated)] backdrop-blur-xl"
          >
            <div className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
              <p
                id={titleId}
                className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]"
              >
                Admin Portal
              </p>
              <Button
                ref={closeRef}
                variant="ghost"
                size="icon"
                aria-label="Close navigation"
                onClick={() => setOpen(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            <AdminNavBody onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      ) : null}
    </div>
  );
}

function AdminTopbar() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const initials =
    user?.display_name
      ?.split(/\s+/)
      .map((p) => p[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() || "AD";

  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-3 border-b border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_72%,transparent)] px-3 backdrop-blur-xl sm:px-4">
      <AdminMobileNav />
      <BrandLogo size={26} className="hidden shrink-0 lg:block" />
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--fg-subtle)]">
          QuantForg
        </p>
        <p className="truncate text-sm font-semibold text-[var(--fg)]">
          Admin Portal
        </p>
      </div>
      <Button asChild variant="outline" size="sm" className="hidden sm:inline-flex">
        <Link href="/dashboard">
          <ArrowLeft className="mr-1.5 h-3.5 w-3.5" aria-hidden />
          Trader workspace
        </Link>
      </Button>
      <span
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[11px] font-semibold text-[var(--fg)]"
        title={user?.email ?? "Operator"}
      >
        {initials}
      </span>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Sign out"
        onClick={() => {
          void logout().finally(() => router.replace("/login"));
        }}
      >
        <LogOut className="h-4 w-4" />
      </Button>
    </header>
  );
}

export function AdminShell({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--shell-sidebar-width", ADMIN_SIDEBAR_WIDTH);
    return () => {
      root.style.removeProperty("--shell-sidebar-width");
    };
  }, []);

  return (
    <div className="relative flex min-h-screen text-[var(--fg)]">
      <aside
        style={{ width: ADMIN_SIDEBAR_WIDTH }}
        className="fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_62%,transparent)] shadow-[4px_0_24px_rgba(2,12,28,0.18)] backdrop-blur-xl lg:flex"
        aria-label="Admin Portal sidebar"
      >
        <div className="shrink-0 border-b border-[var(--border)] px-4 py-4">
          <BrandLogo size={32} />
          <p className="mt-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--fg-subtle)]">
            Enterprise
          </p>
          <p className="text-sm font-semibold text-[var(--fg)]">Admin Portal</p>
          <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
            Internal operations · owner verified
          </p>
        </div>
        <AdminNavBody className="flex-1" />
        <div className="shrink-0 border-t border-[var(--border)] p-3">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 rounded-xl px-3 py-2 text-[12px] font-medium text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
            Return to trader desk
          </Link>
        </div>
      </aside>

      <div
        className="flex min-h-screen min-w-0 flex-1 flex-col"
        style={{ paddingLeft: undefined }}
      >
        <div className="lg:pl-[var(--shell-sidebar-width,16.5rem)]">
          <OfflineBanner showApiDiagnostics />
          <AdminTopbar />
          <main
            id="main-content"
            data-desk="admin"
            className="flex min-h-0 flex-1 flex-col overflow-x-clip overflow-y-auto p-4 sm:p-6 lg:p-8 pb-[calc(1rem+env(safe-area-inset-bottom))]"
            tabIndex={-1}
          >
            <ErrorBoundary>
              <div className="mx-auto w-full max-w-[1600px] qf-motion-desk">
                {children}
              </div>
            </ErrorBoundary>
          </main>
        </div>
      </div>
    </div>
  );
}
