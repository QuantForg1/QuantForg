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
      { href: "/#security", label: "Security" },
    ],
  },
  {
    title: "Legal",
    links: [
      { href: "mailto:support@quantforg.com?subject=Privacy%20Policy", label: "Privacy" },
      { href: "mailto:support@quantforg.com?subject=Terms%20of%20Service", label: "Terms" },
    ],
  },
] as const;

export function SiteFooter() {
  return (
    <footer className="border-t border-[var(--border)] bg-[var(--bg-elevated)]">
      <div className="mx-auto grid w-full max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.2fr_2fr]">
        <div className="max-w-sm space-y-3">
          <BrandLogo size={32} caption="Institutional Trading Intelligence" />
          <p className="text-sm leading-relaxed text-[var(--fg-muted)]">
            Connect your own broker account. QuantForg analyzes markets, applies your approved
            risk settings, and sends orders only through the existing execution path.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-8 text-sm sm:grid-cols-4">
          {COLUMNS.map((column) => (
            <div key={column.title}>
              <p className="mb-3 font-medium text-[var(--fg)]">{column.title}</p>
              <ul className="space-y-2 text-[var(--fg-muted)]">
                {column.links.map((link) => (
                  <li key={link.label}>
                    {link.href.startsWith("/") ? (
                      <Link href={link.href} className="hover:text-[var(--fg)]">
                        {link.label}
                      </Link>
                    ) : (
                      <a href={link.href} className="hover:text-[var(--fg)]">
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
      <div className="border-t border-[var(--border)] px-6 py-4 text-center text-xs text-[var(--fg-subtle)]">
        © {new Date().getFullYear()} QuantForg. Trading can lose capital. This site does not
        promise profits.
      </div>
    </footer>
  );
}
