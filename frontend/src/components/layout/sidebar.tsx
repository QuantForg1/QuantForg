"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronsLeft, ChevronsRight, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  isPrimaryActive,
  primaryRail,
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
  const active = isPrimaryActive(pathname, item);
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
              "qf-rail-link group relative flex items-center gap-2.5 rounded-[var(--radius-sm)] text-[13px] font-medium",
              collapsed ? "justify-center px-0 py-2.5" : "px-2.5 py-2",
              active
                ? "bg-[var(--accent-soft)] text-[var(--accent)] shadow-[inset_2px_0_0_0_var(--accent)]"
                : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]",
            )}
          >
            <Icon
              className={cn(
                "h-4 w-4 shrink-0 transition-transform duration-[var(--duration-fast)] ease-[var(--ease-os)]",
                active && "scale-105",
              )}
              aria-hidden
            />
            {!collapsed ? (
              <>
                <span className="min-w-0 flex-1 truncate">{item.label}</span>
                {item.shortcut ? (
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
  return (
    <nav className="flex-1 overflow-y-auto px-2 py-3" aria-label="Primary">
      {!collapsed ? (
        <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Workspaces
        </p>
      ) : null}

      <ul className="space-y-0.5">
        {primaryRail.map((item) => (
          <PrimaryLink
            key={item.href}
            item={item}
            collapsed={collapsed}
            onNavigate={onNavigate}
          />
        ))}
      </ul>
    </nav>
  );
}

function Brand({ collapsed }: { collapsed?: boolean }) {
  return (
    <div
      className={cn(
        "flex h-12 shrink-0 items-center border-b border-[var(--border)]",
        collapsed ? "justify-center px-2" : "gap-2.5 px-3",
      )}
    >
      <div
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--accent)] text-[var(--accent-fg)]"
        aria-hidden
      >
        <span className="text-xs font-semibold tracking-tight">QF</span>
      </div>
      {!collapsed ? (
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold tracking-tight text-[var(--fg)]">
            QuantForg
          </p>
          <p className="qf-caption truncate">Trading OS</p>
        </div>
      ) : (
        <span className="sr-only">QuantForg Trading OS</span>
      )}
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

  return (
    <aside
      style={{ width }}
      className="relative hidden shrink-0 border-r border-[var(--border)] bg-[var(--bg-elevated)] transition-[width] duration-[var(--duration-os)] ease-[var(--ease-os)] lg:flex lg:flex-col"
      aria-label="Workspace rail"
    >
      <Brand collapsed={chrome.collapsed} />
      <NavBody collapsed={chrome.collapsed} />
      <div className="flex shrink-0 items-center justify-end border-t border-[var(--border)] p-1.5">
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
            className="absolute inset-0 bg-black/50"
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
                <Brand />
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
            <NavBody onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      ) : null}
    </div>
  );
}
