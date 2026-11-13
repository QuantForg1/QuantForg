import Link from "next/link";
import type { ReactNode } from "react";
import { SiteFooter } from "@/components/marketing/site-footer";
import { SiteHeader } from "@/components/marketing/site-header";

const LEGAL_LINKS = [
  { href: "/privacy", label: "Privacy Policy", match: "Privacy Policy" },
  { href: "/terms", label: "Terms of Service", match: "Terms of Service" },
  { href: "/risk-disclosure", label: "Risk Disclosure", match: "Risk Disclosure" },
] as const;

export function LegalDoc({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--fg)]">
      <SiteHeader />
      <main id="main-content" className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-14" tabIndex={-1}>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">
          Legal
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
        <p className="mt-2 text-sm text-[var(--fg-subtle)]">Last updated {updated}</p>

        <nav
          className="mt-6 flex flex-wrap gap-2 border-b border-[var(--border)] pb-4"
          aria-label="Legal documents"
        >
          {LEGAL_LINKS.map((item) => {
            const active = title === item.match;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={
                  active
                    ? "rounded-[var(--radius-sm)] border border-[var(--accent)]/40 bg-[var(--accent-soft)] px-3 py-1.5 text-sm font-medium text-[var(--fg)]"
                    : "rounded-[var(--radius-sm)] border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--fg-muted)] hover:border-[var(--border-strong)] hover:text-[var(--fg)]"
                }
                aria-current={active ? "page" : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="prose-legal mt-8 text-[var(--fg-muted)]">{children}</div>

        <p className="mt-10 text-sm text-[var(--fg-subtle)]">
          Questions?{" "}
          <Link href="/contact" className="text-[var(--accent)] hover:underline">
            Contact QuantForg
          </Link>{" "}
          or email{" "}
          <a href="mailto:support@quantforg.com" className="text-[var(--accent)] hover:underline">
            support@quantforg.com
          </a>
          .
        </p>
      </main>
      <SiteFooter />
    </div>
  );
}
