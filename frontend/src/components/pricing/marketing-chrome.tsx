import Link from "next/link";
import { BrandLogo } from "@/components/brand/brand-logo";

const btn =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-sm)] text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)]";

export const pricingBtnPrimary = `${btn} qf-btn-primary h-11 px-6`;
export const pricingBtnSecondary = `${btn} h-11 px-6 border border-[var(--border-strong)] bg-transparent text-[var(--fg)] hover:bg-[var(--surface-2)]`;
export const pricingBtnGhost = `${btn} h-10 px-4 text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]`;
export const pricingBtnOutline = `${btn} h-10 px-4 border border-[var(--border)] text-[var(--fg)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)]`;

export function PricingHeader({
  active = "pricing",
}: {
  active?: "home" | "pricing" | "purchase" | "contact";
}) {
  return (
    <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 py-5 sm:px-6">
      <Link href="/" className="min-w-0">
        <BrandLogo size={32} priority />
      </Link>
      <nav
        className="hidden items-center gap-6 text-sm text-[var(--fg-muted)] md:flex"
        aria-label="Marketing"
      >
        <Link href="/#features" className="hover:text-[var(--fg)]">
          Features
        </Link>
        <Link
          href="/pricing"
          className={active === "pricing" ? "text-[var(--fg)]" : "hover:text-[var(--fg)]"}
          aria-current={active === "pricing" ? "page" : undefined}
        >
          Pricing
        </Link>
        <Link
          href="/contact"
          className={
            active === "contact" || active === "purchase"
              ? "text-[var(--fg)]"
              : "hover:text-[var(--fg)]"
          }
          aria-current={active === "contact" ? "page" : undefined}
        >
          Contact Sales
        </Link>
      </nav>
      <div className="flex shrink-0 items-center gap-1.5 sm:gap-2" aria-label="Primary">
        <Link href="/login" className={`${pricingBtnGhost} max-sm:px-3`}>
          Sign In
        </Link>
        <Link href="/register" className={`${pricingBtnOutline} max-sm:px-3`}>
          Create account
        </Link>
      </div>
    </header>
  );
}

export function PricingFooter() {
  return (
    <footer className="border-t border-[var(--border)] bg-[var(--bg-elevated)]/80">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-10 md:flex-row md:justify-between">
        <div className="max-w-xs space-y-3">
          <BrandLogo size={32} />
          <p className="text-sm text-[var(--fg-muted)]">
            Institutional trading operating system — licenses activated manually after payment
            verification.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-8 text-sm sm:grid-cols-3">
          <div>
            <p className="mb-3 font-medium text-[var(--fg)]">Product</p>
            <ul className="space-y-2 text-[var(--fg-muted)]">
              <li>
                <Link href="/pricing" className="hover:text-[var(--fg)]">
                  Pricing
                </Link>
              </li>
              <li>
                <Link href="/#features" className="hover:text-[var(--fg)]">
                  Features
                </Link>
              </li>
              <li>
                <a
                  href="mailto:support@quantforg.com?subject=QuantForg%20Documentation"
                  className="hover:text-[var(--fg)]"
                >
                  Documentation
                </a>
              </li>
            </ul>
          </div>
          <div>
            <p className="mb-3 font-medium text-[var(--fg)]">Sales</p>
            <ul className="space-y-2 text-[var(--fg-muted)]">
              <li>
                <Link href="/contact" className="hover:text-[var(--fg)]">
                  Contact Sales
                </Link>
              </li>
              <li>
                <a href="mailto:support@quantforg.com" className="hover:text-[var(--fg)]">
                  Support
                </a>
              </li>
              <li>
                <Link href="/login" className="hover:text-[var(--fg)]">
                  Sign In
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <p className="mb-3 font-medium text-[var(--fg)]">Legal</p>
            <ul className="space-y-2 text-[var(--fg-muted)]">
              <li>
                <a
                  href="mailto:support@quantforg.com?subject=Privacy%20Policy"
                  className="hover:text-[var(--fg)]"
                >
                  Privacy
                </a>
              </li>
              <li>
                <a
                  href="mailto:support@quantforg.com?subject=Terms%20of%20Service"
                  className="hover:text-[var(--fg)]"
                >
                  Terms
                </a>
              </li>
            </ul>
          </div>
        </div>
      </div>
      <div className="border-t border-[var(--border)] px-6 py-4 text-center text-xs text-[var(--fg-subtle)]">
        © {new Date().getFullYear()} QuantForg. All rights reserved.
      </div>
    </footer>
  );
}
