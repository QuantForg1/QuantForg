import type { Metadata } from "next";
import Link from "next/link";
import { SiteFooter } from "@/components/marketing/site-footer";
import { SiteHeader } from "@/components/marketing/site-header";
import { LEARN_PAGES, LEARN_UPDATED, learnPath } from "@/lib/marketing/learn-catalog";
import {
  BILLING_PLANS,
  formatUsd,
  FREE_TRIAL_AVAILABLE,
  PAYMENT_METHOD_LABEL,
} from "@/lib/billing/plans";

export const metadata: Metadata = {
  title: "Product guides",
  description:
    "How QuantForg separates analysis, risk checks, decision records, simulation, and broker results. Software access only.",
  alternates: { canonical: "/learn" },
  openGraph: {
    title: "QuantForg product guides",
    description:
      "Analysis is not an order. A simulation is not broker profit and loss. Plans do not bypass risk checks.",
    url: "/learn",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "QuantForg" }],
  },
};

export default function LearnIndexPage() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-[var(--bg)] text-[var(--fg)]">
      <SiteHeader active="learn" />
      <main id="main-content" className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-14" tabIndex={-1}>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">
          Product guide
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
          How the product behaves
        </h1>
        <p className="mt-4 text-base leading-relaxed text-[var(--fg-muted)]">
          These pages explain the MT5 XAUUSD software that QuantForg already runs. They do not
          add a strategy, a track record, or a free trial.
        </p>
        <p className="mt-2 text-sm text-[var(--fg-subtle)]">Updated {LEARN_UPDATED}</p>

        <ul className="mt-8 space-y-3">
          {LEARN_PAGES.map((page) => (
            <li key={page.slug}>
              <Link
                href={learnPath(page.slug)}
                className="block rounded-[var(--radius-os)] border border-[var(--border)] p-4 hover:border-[var(--accent)]/40"
              >
                <span className="font-medium text-[var(--fg)]">{page.title}</span>
                <span className="mt-1 block text-sm leading-relaxed text-[var(--fg-muted)]">
                  {page.description}
                </span>
              </Link>
            </li>
          ))}
        </ul>

        <section className="mt-10" aria-labelledby="learn-plans">
          <h2 id="learn-plans" className="text-lg font-semibold">
            Plans, from the billing catalog
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-[var(--fg-muted)]">
            Prices below are the software prices in the current catalog. They are not a measure of
            trading results. Payment is {PAYMENT_METHOD_LABEL}. Automatic monthly charging is not
            enabled. A free trial is {FREE_TRIAL_AVAILABLE ? "listed" : "not offered"}.
          </p>
          <ul className="mt-4 space-y-2">
            {BILLING_PLANS.map((plan) => (
              <li key={plan.id} className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                <span className="font-medium text-[var(--fg)]">{plan.name}</span>
                <span className="text-[var(--fg-muted)]">{formatUsd(plan.monthlyPriceUsd)} / month</span>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-sm">
            <Link href="/pricing" className="text-[var(--accent)] hover:underline">
              Open the full pricing page
            </Link>
          </p>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
