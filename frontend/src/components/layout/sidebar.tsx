"use client";

import { useCallback, useEffect, useId, useRef, useState, Fragment, Suspense } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { LifeBuoy, LogOut, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  isPrimaryActive,
  visiblePrimaryRail,
  type PrimaryNavItem,
} from "@/components/layout/nav-config";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  SHELL_SIDEBAR_COLLAPSED,
  SHELL_SIDEBAR_DEFAULT,
} from "@/lib/workspace/shell-chrome";
import { BrandLogo } from "@/components/brand/brand-logo";
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps } from "@/lib/auth/ite-ops-access";

function PrimaryLink({
  item,
  collapsed,
  onNavigate,
  touch,
  index = 0,
}: {
  item: PrimaryNavItem;
  collapsed?: boolean;
  onNavigate?: () => void;
  touch?: boolean;
  index?: number;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const active = isPrimaryActive(pathname, item, searchParams.toString());
  const Icon = item.icon;
  const title = item.hint
    ? `${item.label} — ${item.hint}${item.shortcut ? ` (⌘${item.shortcut})` : ""}`
    : item.label;

  return (
    <li className={touch ? "qf-nav-stagger" : undefined} style={touch ? ({ "--i": index } as React.CSSProperties) : undefined}>
      <Tooltip delayDuration={300}>
        <TooltipTrigger asChild>
          <Link
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            aria-label={title}
            data-active={active}
            className={cn(
              "qf-nav-item group flex items-center gap-3 rounded-xl text-[13px] font-medium outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
              touch ? "px-3.5 py-3" : "px-[11px] py-2.5",
              active
                ? "bg-[var(--accent)] text-[var(--accent-fg)]"
                : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]",
            )}
          >
            <Icon className="qf-nav-icon h-[18px] w-[18px] shrink-0" aria-hidden />
            <span
              className="qf-nav-label min-w-0 flex-1 truncate"
              data-hidden={collapsed ? "true" : "false"}
            >
              {item.label}
            </span>
            {!collapsed && item.railBadge ? (
              <span
                className={cn(
                  "rounded-md px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                  item.railBadge.tone === "danger"
                    ? "bg-[var(--danger)] text-white"
                    : active
                      ? "bg-[color-mix(in_srgb,var(--accent-fg)_18%,transparent)] text-[var(--accent-fg)]"
                      : "bg-[var(--accent)] text-[var(--accent-fg)]",
                )}
              >
                {item.railBadge.label}
              </span>
            ) : null}
            {!collapsed && !touch && item.shortcut && !item.railBadge ? (
              <kbd className="rounded border border-[var(--border)] px-1 py-px font-mono text-[10px] text-[var(--fg-subtle)] opacity-0 transition-opacity duration-[var(--duration-fast)] group-hover:opacity-100 group-focus-visible:opacity-100">
                ⌘{item.shortcut}
              </kbd>
            ) : null}
          </Link>
        </TooltipTrigger>
        <TooltipContent side="right" hidden={!collapsed}>
          {title}
        </TooltipContent>
      </Tooltip>
    </li>
  );
}

function NavBody({
  collapsed,
  onNavigate,
  touch,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
  touch?: boolean;
}) {
  const { user } = useAuth();
  const rail = visiblePrimaryRail(canAccessIteOps(user));
  const [sectionOpen, setSectionOpen] = useState<Record<string, boolean>>({});

  useEffect(() => {
    try {
      const raw = localStorage.getItem("qf.nav.sections.v1");
      if (raw) setSectionOpen(JSON.parse(raw) as Record<string, boolean>);
    } catch {
      /* ignore */
    }
  }, []);

  const toggleSection = useCallback((title: string) => {
    setSectionOpen((prev) => {
      const next = { ...prev, [title]: !(prev[title] ?? true) };
      try {
        localStorage.setItem("qf.nav.sections.v1", JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  return (
    <nav className="flex-1 overflow-y-auto overflow-x-hidden px-2 py-3 [scrollbar-width:thin]" aria-label="Primary">
      <ul className="space-y-1">
        {rail.map((item, index) => {
          const prev = index > 0 ? rail[index - 1] : undefined;
          const sectionChanged = item.section !== prev?.section;
          const sectionTitle = item.section || "";
          const open = !sectionTitle || (sectionOpen[sectionTitle] ?? true);
          const showSection = !collapsed && Boolean(item.section) && sectionChanged;

          if (!collapsed && !open && !sectionChanged) {
            return null;
          }

          return (
            <Fragment key={`${item.href}:${item.label}`}>
              {showSection ? (
                <li className="list-none">
                  <button
                    type="button"
                    onClick={() => toggleSection(sectionTitle)}
                    className={cn(
                      "mb-1 flex w-full items-center justify-between px-2 text-left text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)] hover:text-[var(--fg-muted)]",
                      index > 0 && "mt-3",
                    )}
                    aria-expanded={open}
                  >
                    <span>{item.section}</span>
                    <span className="tabular text-[9px]">{open ? "−" : "+"}</span>
                  </button>
                </li>
              ) : null}
              {collapsed && sectionChanged && index > 0 ? (
                <li aria-hidden className="list-none">
                  <div className="mx-2 my-2 h-px bg-[var(--nav-edge)]" role="separator" />
                </li>
              ) : null}
              {collapsed || open ? (
                <PrimaryLink
                  item={item}
                  collapsed={collapsed}
                  onNavigate={onNavigate}
                  touch={touch}
                  index={index}
                />
              ) : null}
            </Fragment>
          );
        })}
      </ul>
    </nav>
  );
}

/** Mobile drawer only — desktop brand lives once in the top header. */
function MobileBrand() {
  return (
    <div className="flex h-10 shrink-0 items-center gap-2 px-2.5">
      <BrandLogo size={24} />
    </div>
  );
}

export function Sidebar() {
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<number | null>(null);

  const reveal = useCallback(() => {
    if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
    setOpen(true);
  }, []);

  const conceal = useCallback(() => {
    if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setOpen(false), 140);
  }, []);

  useEffect(() => {
    return () => {
      if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
    };
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--shell-sidebar-width", `${SHELL_SIDEBAR_COLLAPSED}px`);
    return () => {
      root.style.removeProperty("--shell-sidebar-width");
    };
  }, []);

  const width = open ? SHELL_SIDEBAR_DEFAULT : SHELL_SIDEBAR_COLLAPSED;

  return (
    <aside
      style={{ width }}
      onPointerEnter={reveal}
      onPointerLeave={conceal}
      onFocusCapture={reveal}
      onBlurCapture={(event) => {
        const next = event.relatedTarget;
        if (next instanceof Node && event.currentTarget.contains(next)) return;
        conceal();
      }}
      className={cn(
        "qf-nav-surface qf-nav-rail fixed inset-y-0 left-0 z-40 hidden overflow-hidden border-r lg:flex lg:flex-col",
        open && "shadow-[24px_0_60px_-24px_rgba(0,0,0,0.55)]",
      )}
      aria-label="Workspace rail"
    >
      <div
        className={cn(
          "shrink-0 border-b border-[var(--nav-edge)]",
          open ? "px-3.5 py-3.5" : "px-2 py-3",
        )}
      >
        <Link
          href="/dashboard"
          className={cn(
            "flex items-center rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
            open ? "gap-2.5" : "justify-center",
          )}
          aria-label="QuantForg overview"
        >
          {open ? <BrandLogo size={32} priority /> : <BrandLogo size={28} wordmark={false} priority />}
        </Link>
      </div>
      <Suspense fallback={<div className="flex-1" aria-hidden />}>
        <NavBody collapsed={!open} />
      </Suspense>
      <div className="shrink-0 border-t border-[var(--nav-edge)] p-2">
        <Link
          href="/support"
          aria-label="Support"
          className="qf-nav-item group flex items-center gap-3 rounded-xl px-[11px] py-2.5 text-[13px] font-medium text-[var(--fg-muted)] outline-none hover:bg-[var(--surface-2)] hover:text-[var(--fg)] focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
        >
          <LifeBuoy className="qf-nav-icon h-[18px] w-[18px] shrink-0" aria-hidden />
          <span className="qf-nav-label truncate" data-hidden={open ? "false" : "true"}>
            Support
          </span>
        </Link>
      </div>
    </aside>
  );
}

export function MobileNav() {
  const [open, setOpenRaw] = useState(false);
  const [closing, setClosing] = useState(false);
  const closeTimerRef = useRef<number | null>(null);
  const touchStartX = useRef<number | null>(null);
  const setOpen = useCallback((next: boolean | ((v: boolean) => boolean)) => {
    setOpenRaw((prev) => {
      const value = typeof next === "function" ? next(prev) : next;
      if (prev && !value) {
        // Play the slide-out before unmounting (skipped for reduced motion).
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (!reduce) {
          setClosing(true);
          if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current);
          closeTimerRef.current = window.setTimeout(() => {
            setOpenRaw(false);
            setClosing(false);
          }, 200);
          return true;
        }
      }
      return value;
    });
  }, []);
  useEffect(
    () => () => {
      if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current);
    },
    [],
  );
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const pathname = usePathname();
  const router = useRouter();
  const { logout } = useAuth();

  useEffect(() => {
    setOpen(false);
  }, [pathname, setOpen]);

  useEffect(() => {
    const toggle = () => setOpen((v) => !v);
    window.addEventListener("qf-nav-toggle", toggle);
    return () => window.removeEventListener("qf-nav-toggle", toggle);
  }, [setOpen]);

  useEffect(() => {
    if (!open) return;
    const trigger = triggerRef.current;
    const prev = document.activeElement as HTMLElement | null;
    const t = window.setTimeout(() => closeRef.current?.focus(), 0);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    // Lock page scroll behind the open drawer (iOS scroll bleed).
    const body = document.body;
    const prevOverflow = body.style.overflow;
    body.style.overflow = "hidden";
    // Close if the viewport grows to desktop while the drawer is open.
    const mq = window.matchMedia("(min-width: 1024px)");
    const onMq = () => mq.matches && setOpen(false);
    mq.addEventListener("change", onMq);
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("keydown", onKey);
      mq.removeEventListener("change", onMq);
      body.style.overflow = prevOverflow;
      (prev ?? trigger)?.focus?.();
    };
  }, [open, setOpen]);

  return (
    <div className="lg:hidden">
      <Button
        ref={triggerRef}
        variant="secondary"
        size="icon"
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        aria-controls="mobile-nav-drawer"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
      </Button>
      {open ? (
        <div className="fixed inset-0 z-[45] lg:hidden">
          <button
            type="button"
            className="qf-nav-scrim absolute inset-0 bg-black/55"
            data-closing={closing}
            aria-label="Dismiss menu"
            onClick={() => setOpen(false)}
          />
          <aside
            id="mobile-nav-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            data-closing={closing}
            onTouchStart={(e) => {
              touchStartX.current = e.touches[0]?.clientX ?? null;
            }}
            onTouchEnd={(e) => {
              const start = touchStartX.current;
              touchStartX.current = null;
              const end = e.changedTouches[0]?.clientX;
              if (start !== null && end !== undefined && start - end > 60) setOpen(false);
            }}
            className="qf-nav-surface qf-nav-drawer absolute left-0 top-0 flex max-w-[20rem] flex-col overflow-hidden border-r"
            style={{
              width: "min(18.5rem, 86vw)",
              paddingTop: "env(safe-area-inset-top)",
              height: "calc(100dvh - var(--shell-mobile-tab-height) - env(safe-area-inset-bottom))",
            }}
          >
            <div className="flex items-center justify-between border-b border-[var(--nav-edge)] py-1.5 pr-2">
              <div id={titleId}>
                <MobileBrand />
              </div>
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
            <Suspense fallback={<div className="flex-1" aria-hidden />}>
              <NavBody touch onNavigate={() => setOpen(false)} />
            </Suspense>
            <div className="shrink-0 border-t border-[var(--nav-edge)] p-2">
              <Button
                type="button"
                variant="ghost"
                className="h-11 w-full justify-start gap-3 rounded-xl px-3.5 text-[13px] text-[var(--fg-muted)]"
                onClick={() => {
                  setOpen(false);
                  void logout().finally(() => router.replace("/login"));
                }}
              >
                <LogOut className="h-[18px] w-[18px]" aria-hidden />
                Sign out
              </Button>
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
