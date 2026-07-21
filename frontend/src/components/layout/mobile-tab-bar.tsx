"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { mobileTabNav } from "@/components/layout/nav-config";

/**
 * Thumb-first mobile bottom navigation — one-hand primary surfaces.
 */
export function MobileTabBar() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t border-[var(--border)] bg-[var(--bg-elevated)]/95 backdrop-blur-md lg:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      aria-label="Primary mobile"
    >
      <ul className="grid h-[4.25rem] grid-cols-5">
        {mobileTabNav.map((item) => {
          const active =
            pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <li key={item.href} className="min-w-0">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "qf-touch-target flex h-full flex-col items-center justify-center gap-0.5 px-1 text-[10px] font-medium transition-colors duration-[var(--duration-os)] ease-[var(--ease-os)]",
                  active
                    ? "text-[var(--accent)]"
                    : "text-[var(--fg-muted)] active:text-[var(--fg)]",
                )}
              >
                <Icon
                  className={cn(
                    "h-5 w-5 shrink-0 transition-transform duration-[var(--duration-os)] ease-[var(--ease-os)]",
                    active && "scale-105",
                  )}
                  aria-hidden
                />
                <span className="truncate">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
