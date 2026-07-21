"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, Menu, Pin, Star, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { appNav } from "@/components/layout/nav-config";
import { Button } from "@/components/ui/button";
import { useNavMemory } from "@/hooks/use-nav-memory";
import { labelForHref } from "@/lib/workspace/nav-memory";

function MemoryLinks({
  title,
  items,
  onNavigate,
}: {
  title: string;
  items: { href: string; label: string }[];
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  if (items.length === 0) return null;
  return (
    <div className="mb-3">
      <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
        {title}
      </p>
      <ul className="space-y-0.5">
        {items.map((item) => {
          const active =
            pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <li key={`${title}-${item.href}`}>
              <Link
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded-md px-2 py-1.5 text-[12px] transition-colors duration-[var(--duration-os)] ease-[var(--ease-os)]",
                  active
                    ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                    : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]",
                )}
              >
                <span className="truncate">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function NavBody({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const memory = useNavMemory();
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    for (const g of appNav) initial[g.title] = true;
    return initial;
  });

  useEffect(() => {
    for (const g of appNav) {
      if (g.items.some((i) => pathname === i.href || pathname.startsWith(`${i.href}/`))) {
        setOpenGroups((prev) => ({ ...prev, [g.title]: true }));
      }
    }
  }, [pathname]);

  const pinCurrent = () => {
    memory.togglePinned({ href: pathname, label: labelForHref(pathname) });
  };
  const favCurrent = () => {
    memory.toggleFavorite({ href: pathname, label: labelForHref(pathname) });
  };

  return (
    <nav className="flex-1 overflow-y-auto px-2 py-3" aria-label="Primary">
      <div className="mb-3 flex items-center gap-1 px-1">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 flex-1 gap-1 px-2 text-[11px]"
          onClick={pinCurrent}
          aria-pressed={memory.isPinned(pathname)}
          title="Pin current page"
        >
          <Pin className="h-3 w-3" aria-hidden />
          {memory.isPinned(pathname) ? "Unpin" : "Pin"}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 flex-1 gap-1 px-2 text-[11px]"
          onClick={favCurrent}
          aria-pressed={memory.isFavorite(pathname)}
          title="Favorite current page"
        >
          <Star className="h-3 w-3" aria-hidden />
          {memory.isFavorite(pathname) ? "Unstar" : "Star"}
        </Button>
      </div>

      <MemoryLinks title="Pinned" items={memory.pinned} onNavigate={onNavigate} />
      <MemoryLinks
        title="Favorites"
        items={memory.favorites.slice(0, 6)}
        onNavigate={onNavigate}
      />
      <MemoryLinks
        title="Recent"
        items={memory.recent.slice(0, 5)}
        onNavigate={onNavigate}
      />

      {appNav.map((group) => {
        const expanded = openGroups[group.title] !== false;
        return (
          <div key={group.title} className="mb-2">
            <button
              type="button"
              className="mb-1 flex w-full items-center justify-between rounded-md px-2 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-muted)] transition-colors duration-[var(--duration-os)] ease-[var(--ease-os)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]"
              aria-expanded={expanded}
              onClick={() =>
                setOpenGroups((prev) => ({
                  ...prev,
                  [group.title]: !expanded,
                }))
              }
            >
              {group.title}
              <ChevronDown
                className={cn(
                  "h-3.5 w-3.5 transition-transform duration-[var(--duration-os)] ease-[var(--ease-os)]",
                  expanded ? "rotate-0" : "-rotate-90",
                )}
                aria-hidden
              />
            </button>
            {expanded ? (
              <ul className="space-y-0.5">
                {group.items.map((item) => {
                  const active =
                    pathname === item.href ||
                    pathname.startsWith(`${item.href}/`);
                  const Icon = item.icon;
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={onNavigate}
                        aria-current={active ? "page" : undefined}
                        title={item.hint}
                        className={cn(
                          "flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px] transition-colors duration-[var(--duration-os)] ease-[var(--ease-os)]",
                          active
                            ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                            : "text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]",
                        )}
                      >
                        <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
                        <span className="truncate">{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </div>
        );
      })}
    </nav>
  );
}

function Brand() {
  return (
    <div className="flex h-12 items-center gap-2.5 border-b border-[var(--border)] px-4">
      <div
        className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--accent)] text-[var(--accent-fg)]"
        aria-hidden
      >
        <span className="text-xs font-semibold tracking-tight">QF</span>
      </div>
      <div>
        <p className="text-sm font-semibold tracking-tight text-[var(--fg)]">
          QuantForg
        </p>
        <p className="qf-caption">Trading OS</p>
      </div>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden w-56 shrink-0 border-r border-[var(--border)] bg-[var(--bg-elevated)] lg:flex lg:flex-col">
      <Brand />
      <NavBody />
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
