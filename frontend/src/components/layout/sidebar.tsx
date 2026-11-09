"use client";

import { useCallback, useEffect, useId, useRef, useState, Fragment, Suspense } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { ChevronsLeft, ChevronsRight, LifeBuoy, Menu, X } from "lucide-react";
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
  loadShellChrome,
  saveShellChrome,
  SHELL_SIDEBAR_COLLAPSED,
  SHELL_SIDEBAR_DEFAULT,
  SHELL_SIDEBAR_MAX,
  SHELL_SIDEBAR_MIN,
  type ShellChromeState,
} from "@/lib/workspace/shell-chrome";
import { BrandLogo } from "@/components/brand/brand-logo";
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps } from "@/lib/auth/ite-ops-access";

function PrimaryLink({
  item,
  collapsed,
  onNavigate,
}: {
  item: PrimaryNavItem;
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const active = isPrimaryActive(pathname, item, searchParams.toString());
  const Icon = item.icon;
  const title = item.hint
    ? `${item.label} — ${item.hint}${item.shortcut ? ` (⌘${item.shortcut})` : ""}`
    : item.label;

  return (
    <li>
      <Tooltip delayDuration={400}>
        <TooltipTrigger asChild>
          <Link
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            aria-label={title}
            className={cn(
              "qf-rail-link group relative flex items-center gap-2.5 rounded-xl text-[13px] font-medium",
              collapsed ? "justify-center px-0 py-2.5" : "px-3 py-2.5",
              active
                ? "bg-[var(--accent)] text-white shadow-[inset_3px_0_0_0_rgba(255,255,255,0.85)]"
                : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]",
            )}
          >
            <Icon
              className="h-4 w-4 shrink-0"
              aria-hidden
            />
            {!collapsed ? (
              <>
                <span className="min-w-0 flex-1 truncate">{item.label}</span>
                {item.railBadge ? (
                  <span
                    className={cn(
                      "rounded-md px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                      item.railBadge.tone === "danger"
                        ? "bg-[var(--danger)] text-white"
                        : active
                          ? "bg-white/20 text-white"
                          : "bg-[var(--accent)] text-white",
                    )}
                  >
                    {item.railBadge.label}
                  </span>
                ) : null}
                {item.shortcut && !item.railBadge ? (
                  <kbd className="rounded border border-[var(--border)] px-1 py-px font-mono text-[10px] text-[var(--fg-subtle)] opacity-0 transition-opacity duration-[var(--duration-fast)] group-hover:opacity-100 group-focus-visible:opacity-100">
                    ⌘{item.shortcut}
                  </kbd>
                ) : null}
              </>
            ) : (
              <span className="sr-only">{item.label}</span>
            )}
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
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
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
    <nav className="flex-1 overflow-y-auto px-2 py-3" aria-label="Primary">
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
                  <div className="my-1.5" role="separator" />
                </li>
              ) : null}
              {collapsed || open ? (
                <PrimaryLink
                  item={item}
                  collapsed={collapsed}
                  onNavigate={onNavigate}
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
    <div className="flex h-12 shrink-0 items-center gap-2.5 px-3">
      <BrandLogo size={28} />
    </div>
  );
}

export function Sidebar() {
  const [chrome, setChrome] = useState<ShellChromeState>({
    collapsed: false,
    width: SHELL_SIDEBAR_DEFAULT,
  });
  const [hydrated, setHydrated] = useState(false);
  const dragging = useRef(false);

  useEffect(() => {
    setChrome(loadShellChrome());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveShellChrome(chrome);
  }, [chrome, hydrated]);

  const toggleCollapsed = useCallback(() => {
    setChrome((prev) => ({ ...prev, collapsed: !prev.collapsed }));
  }, []);

  const onResizeStart = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (chrome.collapsed) return;
      e.preventDefault();
      dragging.current = true;
      const startX = e.clientX;
      const startW = chrome.width;
      const onMove = (ev: PointerEvent) => {
        if (!dragging.current) return;
        const next = Math.min(
          SHELL_SIDEBAR_MAX,
          Math.max(SHELL_SIDEBAR_MIN, startW + (ev.clientX - startX)),
        );
        setChrome((prev) => ({ ...prev, width: next }));
      };
      const onUp = () => {
        dragging.current = false;
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [chrome.collapsed, chrome.width],
  );

  const width = chrome.collapsed ? SHELL_SIDEBAR_COLLAPSED : chrome.width;

  useEffect(() => {
    if (!hydrated) return;
    const root = document.documentElement;
    root.style.setProperty("--shell-sidebar-width", `${width}px`);
    return () => {
      root.style.removeProperty("--shell-sidebar-width");
    };
  }, [width, hydrated]);

  return (
    <aside
      style={{ width }}
      className="fixed inset-y-0 left-0 z-30 hidden border-r border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_62%,transparent)] shadow-[4px_0_24px_rgba(2,12,28,0.18)] backdrop-blur-xl transition-[width] duration-[var(--duration-os)] ease-[var(--ease-os)] lg:flex lg:flex-col"
      aria-label="Workspace rail"
    >
      <div
        className={cn(
          "shrink-0 border-b border-[var(--border)]",
          chrome.collapsed ? "px-2 py-3" : "px-3 py-3.5",
        )}
      >
        <Link
          href="/dashboard"
          className={cn(
            "flex items-center rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
            chrome.collapsed ? "justify-center" : "gap-2.5",
          )}
          aria-label="QuantForg overview"
        >
          {chrome.collapsed ? (
            <BrandLogo size={28} wordmark={false} priority />
          ) : (
            <BrandLogo size={32} priority />
          )}
        </Link>
      </div>
      <Suspense fallback={<div className="flex-1" aria-hidden />}>
        <NavBody collapsed={chrome.collapsed} />
      </Suspense>
      <div className="shrink-0 border-t border-[var(--border)] p-2">
        <Link
          href="/support"
          className={cn(
            "mb-1 flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-[13px] font-medium text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]",
            chrome.collapsed && "justify-center px-0",
          )}
        >
          <LifeBuoy className="h-4 w-4 shrink-0" aria-hidden />
          {chrome.collapsed ? <span className="sr-only">Support</span> : <span>Support</span>}
        </Link>
      <div className="flex shrink-0 items-center justify-end p-1.5">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-8 w-8 px-0"
          aria-label={chrome.collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-pressed={chrome.collapsed}
          onClick={toggleCollapsed}
        >
          {chrome.collapsed ? (
            <ChevronsRight className="h-4 w-4" aria-hidden />
          ) : (
            <ChevronsLeft className="h-4 w-4" aria-hidden />
          )}
        </Button>
      </div>
      </div>
      {!chrome.collapsed ? (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
          tabIndex={0}
          className="absolute inset-y-0 right-0 z-10 w-1 cursor-col-resize touch-none hover:bg-[var(--accent)]/30 focus-visible:bg-[var(--accent)]/40 focus-visible:outline-none"
          onPointerDown={onResizeStart}
          onKeyDown={(e) => {
            if (e.key === "ArrowLeft") {
              e.preventDefault();
              setChrome((prev) => ({
                ...prev,
                width: Math.max(SHELL_SIDEBAR_MIN, prev.width - 8),
              }));
            } else if (e.key === "ArrowRight") {
              e.preventDefault();
              setChrome((prev) => ({
                ...prev,
                width: Math.min(SHELL_SIDEBAR_MAX, prev.width + 8),
              }));
            }
          }}
        />
      ) : null}
    </aside>
  );
}

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

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
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("keydown", onKey);
      (prev ?? trigger)?.focus?.();
    };
  }, [open]);

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
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-[color-mix(in_srgb,var(--bg)_50%,#000)]"
            aria-label="Dismiss menu"
            onClick={() => setOpen(false)}
          />
          <aside
            id="mobile-nav-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="absolute inset-y-0 left-0 flex w-[min(20rem,88vw)] flex-col border-r border-[var(--border)] bg-[var(--bg-elevated)] shadow-[var(--shadow-elevated)]"
          >
            <div className="flex items-center justify-between border-b border-[var(--border)] pr-2">
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
              <NavBody onNavigate={() => setOpen(false)} />
            </Suspense>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
