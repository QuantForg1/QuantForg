"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { BrandLogo } from "@/components/brand/brand-logo";
import { useAuthOptional } from "@/providers/auth-provider";

const LINKS = [
  { href: "/#features", label: "Features" },
  { href: "/#platform", label: "Platform" },
  { href: "/live", label: "Live Market" },
  { href: "/#how-it-works", label: "How it works" },
  { href: "/#strategies", label: "Strategies" },
  { href: "/#security", label: "Security" },
  { href: "/pricing", label: "Pricing" },
] as const;

export function SiteHeader({
  active,
}: {
  active?: "home" | "pricing" | "purchase" | "contact" | "live" | "billing";
}) {
  const [open, setOpen] = useState(false);
  const auth = useAuthOptional();
  const isAuthenticated = auth?.isAuthenticated ?? false;
  const loading = auth?.loading ?? false;

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_55%,transparent)] backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link href="/" className="min-w-0" onClick={() => setOpen(false)}>
          <BrandLogo size={34} priority caption={false} />
        </Link>
        <nav className="hidden items-center gap-5 text-sm text-[var(--fg-muted)] lg:flex" aria-label="Marketing">
          {LINKS.map((item) => {
            const current =
              (item.href === "/pricing" && active === "pricing") ||
              (item.href === "/live" && active === "live");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={current ? "text-[var(--fg)]" : "hover:text-[var(--fg)]"}
                aria-current={current ? "page" : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="flex shrink-0 items-center gap-2">
          {!loading && isAuthenticated ? (
            <>
              <Link
                href="/dashboard"
                className="hidden h-10 items-center rounded-[var(--radius-sm)] border border-[var(--border)] px-4 text-sm font-medium text-[var(--fg)] hover:bg-[color-mix(in_srgb,var(--surface-2)_70%,transparent)] sm:inline-flex"
              >
                Dashboard
              </Link>
              <Link
                href="/billing/invoices"
                className="hidden h-10 items-center rounded-[var(--radius-sm)] border border-[var(--border)] px-4 text-sm font-medium text-[var(--fg)] hover:bg-[color-mix(in_srgb,var(--surface-2)_70%,transparent)] md:inline-flex"
              >
                Invoices
              </Link>
              <Link
                href="/settings"
                className="qf-btn-cta inline-flex h-10 items-center rounded-[var(--radius-sm)] px-4 text-sm font-semibold"
              >
                Settings
              </Link>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="hidden h-10 items-center rounded-[var(--radius-sm)] border border-[var(--border)] px-4 text-sm font-medium text-[var(--fg)] hover:bg-[color-mix(in_srgb,var(--surface-2)_70%,transparent)] sm:inline-flex"
              >
                Sign In
              </Link>
              <Link
                href="/register"
                className="qf-btn-cta inline-flex h-10 items-center rounded-[var(--radius-sm)] px-4 text-sm font-semibold"
              >
                Connect Your Broker
              </Link>
            </>
          )}
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-[var(--radius-sm)] border border-[var(--border)] text-[var(--fg)] lg:hidden"
            aria-expanded={open}
            aria-controls="marketing-menu"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            <span className="sr-only">{open ? "Close menu" : "Open menu"}</span>
          </button>
        </div>
      </div>
      {open ? (
        <nav id="marketing-menu" className="border-t border-[var(--border)] px-4 py-3 lg:hidden" aria-label="Marketing mobile">
          <ul className="space-y-1">
            {LINKS.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="block rounded-[var(--radius-sm)] px-3 py-2 text-sm text-[var(--fg-muted)] hover:bg-[color-mix(in_srgb,var(--surface-2)_70%,transparent)] hover:text-[var(--fg)]"
                  onClick={() => setOpen(false)}
                >
                  {item.label}
                </Link>
              </li>
            ))}
            {!loading && isAuthenticated ? (
              <>
                <li>
                  <Link
                    href="/dashboard"
                    className="block rounded-[var(--radius-sm)] px-3 py-2 text-sm text-[var(--fg)]"
                    onClick={() => setOpen(false)}
                  >
                    Dashboard
                  </Link>
                </li>
                <li>
                  <Link
                    href="/billing/invoices"
                    className="block rounded-[var(--radius-sm)] px-3 py-2 text-sm text-[var(--fg)]"
                    onClick={() => setOpen(false)}
                  >
                    Invoices
                  </Link>
                </li>
              </>
            ) : (
              <li>
                <Link
                  href="/login"
                  className="block rounded-[var(--radius-sm)] px-3 py-2 text-sm text-[var(--fg)] hover:bg-[color-mix(in_srgb,var(--surface-2)_70%,transparent)] sm:hidden"
                  onClick={() => setOpen(false)}
                >
                  Sign In
                </Link>
              </li>
            )}
          </ul>
        </nav>
      ) : null}
    </header>
  );
}
