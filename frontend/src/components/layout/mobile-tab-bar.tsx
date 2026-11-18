"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { isPrimaryActive, mobileTabNav, primaryRail } from "@/components/layout/nav-config";

/**
 * Thumb-first mobile bottom navigation — primary desks only.
 */
export function MobileTabBar() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-50 w-full max-w-[100vw] overflow-x-clip border-t border-[var(--border)] bg-[var(--bg-elevated)] lg:hidden"
      style={{
        paddingBottom: "max(env(safe-area-inset-bottom), 0px)",
      }}
      aria-label="Primary mobile"
    >
      <ul
        className="grid grid-cols-5"
        style={{ height: "var(--shell-mobile-tab-height)" }}
      >
        {mobileTabNav.map((item) => {
          const desk = primaryRail.find((d) => d.href === item.href);
          const active = desk
            ? isPrimaryActive(pathname, desk)
            : pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <li key={item.href} className="min-w-0">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "qf-touch-target relative flex h-full flex-col items-center justify-center gap-0.5 px-1 text-[11px] font-medium tracking-tight transition-colors duration-[var(--duration-fast)] ease-[var(--ease-os)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
                  active
                    ? "text-[var(--accent)]"
                    : "text-[var(--fg-muted)] active:text-[var(--fg)]",
                )}
              >
                <span
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-lg transition-colors duration-[var(--duration-os)] ease-[var(--ease-os)]",
                    active && "bg-[var(--accent-soft)]",
                  )}
                >
                  <Icon
                    className={cn(
                      "h-5 w-5 shrink-0 transition-transform duration-[var(--duration-os)] ease-[var(--ease-os)]",
                      active && "scale-105",
                    )}
                    aria-hidden
                  />
                </span>
                <span className="max-w-full truncate">{item.label}</span>
                {active ? (
                  <span
                    className="absolute inset-x-3 top-0 h-0.5 rounded-b-full bg-[var(--accent)]"
                    aria-hidden
                  />
                ) : null}
              </Link>
            </li>
          );
        })}
        <li className="min-w-0">
          <button
            type="button"
            className="qf-touch-target relative flex h-full w-full flex-col items-center justify-center gap-0.5 px-1 text-[11px] font-medium tracking-tight text-[var(--fg-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            onClick={() => window.dispatchEvent(new Event("qf-nav-toggle"))}
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg">
              <Menu className="h-5 w-5" aria-hidden />
            </span>
            <span className="max-w-full truncate">Menu</span>
          </button>
        </li>
      </ul>
    </nav>
  );
}
