"use client";

import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

/** Shared surface class — Phase 1 card language (Book / Terminal). */
export const DESK_PANEL_SURFACE =
  "qf-panel-live rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)]";

/**
 * Phase 1 desk panel — single card language for all OS desks.
 * Prefer this over ad-hoc bordered sections.
 */
export function DeskPanel({
  title,
  subtitle,
  actions,
  focused,
  className,
  bodyClassName,
  children,
  collapsible,
  collapsed,
  onToggle,
  "aria-label": ariaLabel,
}: {
  title?: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  focused?: boolean;
  className?: string;
  bodyClassName?: string;
  children?: ReactNode;
  collapsible?: boolean;
  collapsed?: boolean;
  onToggle?: () => void;
  "aria-label"?: string;
}) {
  const label = ariaLabel ?? title;

  return (
    <section
      className={cn(
        "flex min-h-0 flex-col",
        DESK_PANEL_SURFACE,
        focused && "ring-1 ring-[var(--accent)]",
        className,
      )}
      data-focused={focused ? "true" : undefined}
      aria-label={label}
    >
      {title || actions || collapsible ? (
        <header
          className={cn(
            "flex shrink-0 items-center justify-between gap-2 border-b border-[var(--border)] px-[var(--space-3)] py-[var(--space-2)]",
            collapsible && "cursor-pointer",
          )}
        >
          <div className="min-w-0 flex-1">
            {title ? (
              <div className="flex items-center gap-2">
                {collapsible ? (
                  <button
                    type="button"
                    className="flex min-w-0 items-center gap-1.5 text-left"
                    aria-expanded={!collapsed}
                    onClick={onToggle}
                  >
                    <ChevronDown
                      className={cn(
                        "h-3.5 w-3.5 shrink-0 text-[var(--fg-subtle)] transition-transform duration-[var(--duration-os)] ease-[var(--ease-os)]",
                        collapsed && "-rotate-90",
                      )}
                      aria-hidden
                    />
                    <h2 className="qf-label truncate text-[var(--fg)]">{title}</h2>
                  </button>
                ) : (
                  <h2 className="qf-label truncate text-[var(--fg)]">{title}</h2>
                )}
              </div>
            ) : null}
            {subtitle && !collapsed ? (
              <div className="mt-0.5 text-[var(--fg-subtle)]">{subtitle}</div>
            ) : null}
          </div>
          {actions && !collapsed ? (
            <div className="flex shrink-0 items-center gap-1">{actions}</div>
          ) : null}
        </header>
      ) : null}
      {!collapsed ? (
        <div
          className={cn(
            "min-h-0 flex-1 overflow-auto p-[var(--space-3)]",
            bodyClassName,
          )}
        >
          {children}
        </div>
      ) : null}
    </section>
  );
}

/**
 * Shared OS desk toolbar — matches Terminal / Book Phase 1 chrome.
 */
export function DeskShellHeader({
  title,
  subtitle,
  meta,
  actions,
}: {
  title: string;
  subtitle?: string;
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex h-9 items-center justify-between gap-2 border-b border-[var(--border)] bg-[var(--bg-elevated)] px-3">
      <div className="flex min-w-0 items-center gap-2 sm:gap-3">
        <h1 className="shrink-0 text-xs font-semibold tracking-tight text-[var(--fg)]">
          {title}
        </h1>
        {subtitle ? (
          <span className="qf-caption hidden truncate sm:inline">{subtitle}</span>
        ) : null}
        {meta}
      </div>
      {actions ? (
        <div className="flex shrink-0 items-center gap-0.5">{actions}</div>
      ) : null}
    </div>
  );
}
