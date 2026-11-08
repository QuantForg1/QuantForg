import type { Metadata } from "next";
import Link from "next/link";
import { Check, Shield } from "lucide-react";
import { BrandMark } from "@/components/brand/brand-logo";
import { PricingFaq } from "@/components/pricing/pricing-faq";
import {
  PricingFooter,
  PricingHeader,
  pricingBtnPrimary,
  pricingBtnSecondary,
} from "@/components/pricing/marketing-chrome";
import {
  ANNUAL_BILLING_SUPPORTED,
  BILLING_PLANS,
  BILLING_PROVIDER,
  formatUsd,
} from "@/lib/billing/plans";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "QuantForg subscription plans for trading technology access — Starter, Professional, and Premium. Software access only; trading outcomes are not guaranteed.",
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "QuantForg Pricing",
    description:
      "Proposed monthly plans for QuantForg trading technology platform access. No profit guarantees.",
    url: "/pricing",
  },
};

const comparisonRows: { feature: string; starter: string; professional: string; premium: string }[] =
  [
    {
      feature: "Platform workspace",
      starter: "Included",
      professional: "Included",
      premium: "Included",
    },
    {
      feature: "MT5 connection workflows",
      starter: "Included",
      professional: "Included",
      premium: "Included",
    },
    {
      feature: "Research & strategy tools",
      starter: "Core",
      professional: "Expanded",
      premium: "Expanded",
    },
    {
      feature: "Portfolio surfaces",
      starter: "Essential",
      professional: "Full",
      premium: "Full",
    },
    {
      feature: "Support",
      starter: "Email",
      professional: "Priority",
      premium: "Enhanced",
    },
    {
      feature: "Onboarding assistance",
      starter: "Self-serve",
      professional: "Guided",
      premium: "Enhanced",
    },
  ];

export default function PricingPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[var(--bg)] text-[var(--fg)]">
      <PricingHeader />
      <main id="main-content" tabIndex={-1}>
        <section className="relative mx-auto max-w-6xl px-4 pb-10 pt-14 sm:px-6 sm:pt-20">
          <div className="mx-auto max-w-3xl text-center">
            <BrandMark size={72} priority className="mx-auto" />
            <p className="mt-6 text-xs font-semibold uppercase tracking-[0.18em] text-[var(--accent)]">
              Subscription plans
            </p>
            <h1 className="mt-3 font-[family-name:var(--font-display)] text-4xl font-semibold tracking-tight sm:text-5xl">
              Choose the access that fits your desk
            </h1>
            <p className="mt-4 text-base leading-relaxed text-[var(--fg-muted)] sm:text-lg">
              QuantForg is trading technology sold through subscription. Plans describe software
              access and support — not trading profits, returns, or risk-free outcomes.
            </p>
            {!ANNUAL_BILLING_SUPPORTED ? (
              <p className="mt-3 text-sm text-[var(--fg-subtle)]">
                Monthly pricing shown. Annual billing will appear only when a recurring payment
                provider supports it.
              </p>
            ) : null}
          </div>

          <div className="mt-12 grid gap-5 lg:grid-cols-3">
            {BILLING_PLANS.map((plan) => (
              <article
                key={plan.id}
                className={`qf-glass-card relative flex flex-col p-6 sm:p-7 ${
                  plan.highlighted ? "ring-1 ring-[var(--accent)]" : ""
                }`}
              >
                {plan.highlighted ? (
                  <span className="qf-lifetime-badge absolute -top-3 left-1/2 -translate-x-1/2">
                    Most popular
                  </span>
                ) : null}
                <h2 className="text-xl font-semibold tracking-tight">{plan.name}</h2>
                <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">
                  {plan.positioning}
                </p>
                <p className="mt-6 flex items-baseline gap-1">
                  <span className="qf-num-lg text-4xl font-semibold">
                    {formatUsd(plan.monthlyPriceUsd)}
                  </span>
                  <span className="text-sm text-[var(--fg-subtle)]">/ month</span>
                </p>
                <p className="mt-1 text-xs text-[var(--fg-subtle)]">
                  Proposed starting price · billed monthly when checkout is enabled
                </p>
                <ul className="mt-6 flex-1 space-y-2.5">
                  {plan.entitlements.map((item) => (
                    <li key={item} className="flex gap-2 text-sm text-[var(--fg-muted)]">
                      <Check
                        className="mt-0.5 h-4 w-4 shrink-0 text-[var(--accent)]"
                        aria-hidden
                      />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
                <div className="mt-8 space-y-2">
                  <Link
                    href={`/register?plan=${plan.id}`}
                    className={`${plan.highlighted ? pricingBtnPrimary : pricingBtnSecondary} w-full`}
                  >
                    {plan.ctaLabel}
                  </Link>
                  <Link
                    href={`/contact?plan=${plan.id}`}
                    className="block text-center text-xs text-[var(--fg-subtle)] hover:text-[var(--fg-muted)]"
                  >
                    Talk to sales about {plan.name}
                  </Link>
                </div>
              </article>
            ))}
          </div>

          <div className="mt-8 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)]/60 p-5 sm:p-6">
            <div className="flex gap-3">
              <Shield className="mt-0.5 h-5 w-5 shrink-0 text-[var(--accent)]" aria-hidden />
              <div className="space-y-2 text-sm leading-relaxed text-[var(--fg-muted)]">
                <p className="font-medium text-[var(--fg)]">Payment status</p>
                <p>{BILLING_PROVIDER.note}</p>
                <p>
                  Existing licenses remain managed through QuantForg operations after payment
                  verification. Selecting a plan never grants paid access by itself.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6" aria-labelledby="compare-heading">
          <h2 id="compare-heading" className="text-center text-2xl font-semibold tracking-tight">
            Compare plans
          </h2>
          <div className="mt-8 overflow-x-auto rounded-[var(--radius-os)] border border-[var(--border)]">
            <table className="w-full min-w-[640px] border-collapse text-left text-sm">
              <thead className="bg-[var(--surface)]">
                <tr>
                  <th className="px-4 py-3 font-medium">Capability</th>
                  <th className="px-4 py-3 font-medium">Starter</th>
                  <th className="px-4 py-3 font-medium">Professional</th>
                  <th className="px-4 py-3 font-medium">Premium</th>
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map((row) => (
                  <tr key={row.feature} className="border-t border-[var(--border)]">
                    <th scope="row" className="px-4 py-3 font-medium text-[var(--fg)]">
                      {row.feature}
                    </th>
                    <td className="px-4 py-3 text-[var(--fg-muted)]">{row.starter}</td>
                    <td className="px-4 py-3 text-[var(--fg-muted)]">{row.professional}</td>
                    <td className="px-4 py-3 text-[var(--fg-muted)]">{row.premium}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-20 sm:px-6" aria-labelledby="pricing-faq">
          <h2 id="pricing-faq" className="mb-8 text-center text-2xl font-semibold tracking-tight">
            Pricing FAQ
          </h2>
          <PricingFaq />
        </section>
      </main>
      <PricingFooter />
    </div>
  );
}
