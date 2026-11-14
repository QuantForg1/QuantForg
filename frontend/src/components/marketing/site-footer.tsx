import Link from "next/link";
import { BrandLogo } from "@/components/brand/brand-logo";

const COLUMNS = [
  {
    title: "Product",
    links: [
      { href: "/#features", label: "Features" },
      { href: "/#platform", label: "Platform" },
      { href: "/#how-it-works", label: "How It Works" },
      { href: "/#strategies", label: "Strategies" },
      { href: "/pricing", label: "Pricing" },
    ],
  },
  {
    title: "Platform",
    links: [
      { href: "/live", label: "Live Market" },
      { href: "/#brokers", label: "Brokers" },
      { href: "/#security", label: "Security" },
      { href: "/#risk", label: "Risk" },
      { href: "/#faq", label: "FAQ" },
    ],
  },
  {
    title: "Resources",
    links: [
      { href: "/contact", label: "Contact Sales" },
      { href: "mailto:support@quantforg.com", label: "Support" },
      {
        href: "mailto:support@quantforg.com?subject=QuantForg%20Documentation",
        label: "Documentation",
      },
    ],
  },
  {
    title: "Company",
    links: [
      { href: "/login", label: "Sign In" },
      { href: "/register", label: "Create account" },
      { href: "/contact", label: "Contact" },
    ],
  },
  {
    title: "Legal",
    links: [
      { href: "/privacy", label: "Privacy" },
      { href: "/terms", label: "Terms" },
      { href: "/risk-disclosure", label: "Risk Disclosure" },
    ],
  },
] as const;

export function SiteFooter() {
  return (
    <footer className="border-t border-[var(--border)] bg-[color-mix(in_srgb,var(--bg-elevated)_70%,rgba(4,20,38,0.92))] backdrop-blur-xl">
      <div className="mx-auto grid w-full max-w-6xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[minmax(220px,1.15fr)_minmax(0,2.2fr)] lg:gap-12">
        <div className="max-w-sm space-y-4">
          <BrandLogo size={34} caption={false} />
          <p className="text-sm leading-relaxed text-[var(--fg-muted)]">
            QuantForg is institutional trading technology sold by subscription. Connect your own
            MetaTrader 5 broker account where supported. Software access is not a promise of trading
            profits.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <Link
              href="/register"
              className="qf-btn-primary inline-flex h-10 items-center rounded-[var(--radius-sm)] px-4 text-sm font-semibold"
            >
              Connect Your Broker
            </Link>
            <Link
              href="/pricing"
              className="inline-flex h-10 items-center rounded-[var(--radius-sm)] border border-[var(--border-strong)] px-4 text-sm font-medium text-[var(--fg)] hover:bg-[color-mix(in_srgb,var(--surface-2)_70%,transparent)]"
            >
              View Pricing
            </Link>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-x-6 gap-y-8 text-sm sm:grid-cols-3 lg:grid-cols-5">
          {COLUMNS.map((column) => (
            <div key={column.title}>
              <p className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-[var(--fg)]">
                {column.title}
              </p>
              <ul className="space-y-2.5 text-[var(--fg-muted)]">
                {column.links.map((link) => (
                  <li key={`${column.title}-${link.label}`}>
                    {link.href.startsWith("/") ? (
                      <Link
                        href={link.href}
                        className="transition-colors hover:text-[var(--fg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                      >
                        {link.label}
                      </Link>
                    ) : (
                      <a
                        href={link.href}
                        className="transition-colors hover:text-[var(--fg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                      >
                        {link.label}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
      <div className="border-t border-[var(--border)]">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-2 px-4 py-4 text-xs text-[var(--fg-subtle)] sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>© 2026 QuantForg. Trading can lose capital. This site does not promise profits.</p>
          <p className="sm:text-right">QF · Institutional trading technology</p>
        </div>
      </div>
    </footer>
  );
}
