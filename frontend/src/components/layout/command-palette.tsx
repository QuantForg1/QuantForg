"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { Clock, Pin, Star } from "lucide-react";
import { commandItems, appNav } from "@/components/layout/nav-config";
import { useNavMemory } from "@/hooks/use-nav-memory";
import { labelForHref } from "@/lib/workspace/nav-memory";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const titleId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const memory = useNavMemory();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  useEffect(() => {
    if (!open) {
      setQuery("");
      return;
    }
    const t = window.setTimeout(() => inputRef.current?.focus(), 0);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onOpenChange(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onOpenChange]);

  const allPages = useMemo(() => {
    const fromNav = appNav.flatMap((g) => g.items);
    const map = new Map<string, { href: string; label: string; hint?: string }>();
    for (const item of [...fromNav, ...commandItems]) {
      map.set(item.href, { href: item.href, label: item.label, hint: item.hint });
    }
    return [...map.values()];
  }, []);

  const go = (href: string, label?: string) => {
    onOpenChange(false);
    memory.recordPage({ href, label: label ?? labelForHref(href) });
    router.push(href);
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/45 p-4 pt-[10vh] backdrop-blur-[6px]"
      role="presentation"
    >
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        aria-label="Close command palette"
        onClick={() => onOpenChange(false)}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative z-10 w-full max-w-xl qf-elevate"
      >
        <h2 id={titleId} className="sr-only">
          Command palette
        </h2>
        <Command
          className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] shadow-[var(--shadow-elevated)]"
          label="Global search"
        >
          <Command.Input
            ref={inputRef}
            value={query}
            onValueChange={setQuery}
            placeholder="Jump to page, symbol, or action…"
            aria-label="Search pages, symbols, and actions"
            className="h-12 w-full border-b border-[var(--border)] bg-transparent px-4 text-sm text-[var(--fg)] outline-none placeholder:text-[var(--fg-muted)]"
          />
          <Command.List className="max-h-[min(24rem,55vh)] overflow-y-auto p-1.5">
            <Command.Empty className="px-3 py-8 text-center text-sm text-[var(--fg-muted)]">
              No matches.
            </Command.Empty>

            {memory.pinned.length > 0 ? (
              <Command.Group heading="Pinned" className="qf-cmd-group">
                {memory.pinned.map((item) => (
                  <Command.Item
                    key={`pin-${item.href}`}
                    value={`pinned ${item.label} ${item.href}`}
                    onSelect={() => go(item.href, item.label)}
                    className="qf-cmd-item"
                  >
                    <Pin className="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" aria-hidden />
                    <span className="truncate">{item.label}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}

            {memory.favorites.length > 0 ? (
              <Command.Group heading="Favorites" className="qf-cmd-group">
                {memory.favorites.map((item) => (
                  <Command.Item
                    key={`fav-${item.href}`}
                    value={`favorite ${item.label} ${item.href}`}
                    onSelect={() => go(item.href, item.label)}
                    className="qf-cmd-item"
                  >
                    <Star className="h-3.5 w-3.5 shrink-0 text-[var(--warning)]" aria-hidden />
                    <span className="truncate">{item.label}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}

            {memory.recent.length > 0 ? (
              <Command.Group heading="Recent" className="qf-cmd-group">
                {memory.recent.slice(0, 6).map((item) => (
                  <Command.Item
                    key={`recent-${item.href}`}
                    value={`recent ${item.label} ${item.href}`}
                    onSelect={() => go(item.href, item.label)}
                    className="qf-cmd-item"
                  >
                    <Clock className="h-3.5 w-3.5 shrink-0" aria-hidden />
                    <span className="truncate">{item.label}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}

            <Command.Group heading="Instrument" className="qf-cmd-group">
              <Command.Item
                value={`symbol ${TRADING_SYMBOL} gold xauusd`}
                onSelect={() => go("/terminal", "Terminal")}
                className="qf-cmd-item"
              >
                <span className="tabular text-[var(--accent)]">{TRADING_SYMBOL}</span>
                <span className="text-[var(--fg-subtle)]">XAUUSD only</span>
              </Command.Item>
            </Command.Group>

            <Command.Group heading="Pages" className="qf-cmd-group">
              {allPages.map((item) => {
                const Icon =
                  commandItems.find((c) => c.href === item.href)?.icon ??
                  appNav.flatMap((g) => g.items).find((c) => c.href === item.href)?.icon;
                return (
                  <Command.Item
                    key={`page-${item.href}`}
                    value={`${item.label} ${item.hint ?? ""} ${item.href}`}
                    onSelect={() => go(item.href, item.label)}
                    className="qf-cmd-item"
                  >
                    {Icon ? <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden /> : null}
                    <span className="min-w-0 flex-1 truncate">{item.label}</span>
                    {item.hint ? (
                      <span className="hidden truncate text-[11px] text-[var(--fg-subtle)] sm:inline">
                        {item.hint}
                      </span>
                    ) : null}
                  </Command.Item>
                );
              })}
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
