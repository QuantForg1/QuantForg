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
  PAYMENT_METHOD_LABEL,
  PLAN_COMPARISON_ROWS,
  UNPAID_ACCESS,
} from "@/lib/billing/plans";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "QuantForg subscription plans for Institutional AI Trading Platform access — Starter, Professional, and Premium. Software access only; trading outcomes are not guaranteed.",
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "QuantForg Pricing — Institutional AI Trading Platform",
    description:
      "Proposed monthly plans for QuantForg platform access. No profit guarantees.",
    url: "/pricing",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "QuantForg" }],
  },
};

export default function PricingPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[var(--bg)] text-[var(--fg)]">
      <PricingHeader />
      <main id="main-content" tabIndex={-1}>
        <section className="relative mx-auto max-w-6xl px-4 pb-8 pt-12 sm:px-6 sm:pb-10 sm:pt-16">
          <div className="mx-auto max-w-3xl text-center">
            <BrandMark size={64} priority className="mx-auto" />
            <p className="mt-5 text-xs font-semibold uppercase tracking-[0.18em] text-[var(--accent)]">
              Subscription plans
            </p>
            <h1 className="mt-3 font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight sm:text-5xl">
              Choose the access that fits your desk
            </h1>
            <p className="mt-4 text-base leading-relaxed text-[var(--fg-muted)] sm:text-lg">
              QuantForg is trading technology sold through subscription. Plans describe software
              access and support — not trading profits, returns, or risk-free outcomes.
            </p>
          </div>

          <div className="mx-auto mt-8 max-w-3xl rounded-[var(--radius-os)] border border-[var(--accent)]/35 bg-[var(--accent-soft)] px-4 py-4 sm:px-6">
            <p className="text-center text-sm font-semibold text-[var(--fg)]">
              Connect and verify your broker for free. Subscribe to start the robot.
            </p>
            <ul className="mx-auto mt-3 grid max-w-xl gap-1.5 text-sm sm:grid-cols-2">
              {UNPAID_ACCESS.map((row) => (
                <li
                  key={row.feature}
                  className={`flex gap-2 ${row.allowed ? "text-[var(--fg-muted)]" : "text-[var(--fg-subtle)]"}`}
                >
                  <span aria-hidden className={row.allowed ? "text-[var(--accent)]" : ""}>
                    {row.allowed ? "✓" : "—"}
                  </span>
                  <span>
                    {row.feature}
                    {row.allowed ? "" : " · subscription required"}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {!ANNUAL_BILLING_SUPPORTED ? (
            <p className="mx-auto mt-4 max-w-3xl text-center text-sm text-[var(--fg-subtle)]">
              Monthly pricing shown. Automatic monthly crypto charging is not enabled — renew with
              a new invoice via {PAYMENT_METHOD_LABEL}.
            </p>
          ) : null}

          <div className="mt-10 grid items-stretch gap-4 sm:gap-5 lg:grid-cols-3">
            {BILLING_PLANS.map((plan) => (
              <article
                key={plan.id}
                className={`qf-glass-card relative flex h-full flex-col p-5 sm:p-6 ${
                  plan.highlighted ? "ring-1 ring-[var(--accent)]" : ""
                }`}
              >
                <div className="min-h-[1.75rem]">
                  {plan.highlighted ? (
                    <span className="qf-lifetime-badge absolute -top-3 left-1/2 -translate-x-1/2">
                      Most popular
                    </span>
                  ) : null}
                </div>
                <h2 className="text-xl font-semibold tracking-tight">{plan.name}</h2>
                <p className="mt-2 min-h-[3.2rem] text-sm leading-relaxed text-[var(--fg-muted)]">
                  {plan.positioning}
                </p>
                <p className="mt-5 flex items-baseline gap-1">
                  <span className="qf-num-lg text-4xl font-semibold">
                    {formatUsd(plan.monthlyPriceUsd)}
                  </span>
                  <span className="text-sm text-[var(--fg-subtle)]">/ month</span>
                </p>
                <p className="mt-1 text-xs text-[var(--fg-subtle)]">
                  Monthly USD price · paid via {PAYMENT_METHOD_LABEL}
                </p>
                <ul className="mt-5 flex-1 space-y-2">
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
                <div className="mt-6 space-y-2">
                  <Link
                    href={`/billing/checkout?plan=${plan.id}`}
                    className={`${plan.highlighted ? pricingBtnPrimary : pricingBtnSecondary} w-full`}
                  >
                    {plan.ctaLabel}
                  </Link>
                  <Link
                    href={`/register?plan=${plan.id}`}
                    className="block text-center text-xs text-[var(--fg-subtle)] hover:text-[var(--fg-muted)]"
                  >
                    Create account first, then checkout
                  </Link>
                </div>
              </article>
            ))}
          </div>

          <div className="mt-6 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)]/60 p-5 sm:p-6">
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

        <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6" aria-labelledby="compare-heading">
          <h2 id="compare-heading" className="text-center text-2xl font-semibold tracking-tight">
            Compare plans
          </h2>
          <div className="mt-6 overflow-x-auto rounded-[var(--radius-os)] border border-[var(--border)]">
            <table className="w-full min-w-[720px] border-collapse text-left text-sm">
              <thead className="bg-[var(--surface)]">
                <tr>
                  <th className="px-4 py-3 font-medium">Capability</th>
                  <th className="px-4 py-3 font-medium">Without subscription</th>
                  <th className="px-4 py-3 font-medium">Starter</th>
                  <th className="px-4 py-3 font-medium">Professional</th>
                  <th className="px-4 py-3 font-medium">Premium</th>
                </tr>
              </thead>
              <tbody>
                {PLAN_COMPARISON_ROWS.map((row) => (
                  <tr key={row.feature} className="border-t border-[var(--border)]">
                    <th scope="row" className="px-4 py-3 font-medium text-[var(--fg)]">
                      {row.feature}
                    </th>
                    <td className="px-4 py-3 text-[var(--fg-muted)]">{row.unpaid}</td>
                    <td className="px-4 py-3 text-[var(--fg-muted)]">{row.starter}</td>
                    <td className="px-4 py-3 text-[var(--fg-muted)]">{row.professional}</td>
                    <td className="px-4 py-3 text-[var(--fg-muted)]">{row.premium}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-4 sm:px-6" aria-labelledby="pricing-limits">
          <h2 id="pricing-limits" className="text-center text-2xl font-semibold tracking-tight">
            Read the limits before you subscribe
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-sm leading-relaxed text-[var(--fg-muted)]">
            There is no free trial. A plan does not bypass a risk check, and a browser return from
            checkout does not activate paid access.
          </p>
          <ul className="mx-auto mt-6 grid max-w-3xl gap-3 sm:grid-cols-2">
            <li>
              <Link href="/learn/analysis-versus-order" className="text-sm text-[var(--accent)] hover:underline">
                Analysis is not an order
              </Link>
            </li>
            <li>
              <Link href="/learn/stops-and-daily-loss" className="text-sm text-[var(--accent)] hover:underline">
                Stops and the daily-loss halt
              </Link>
            </li>
            <li>
              <Link href="/learn/decision-record" className="text-sm text-[var(--accent)] hover:underline">
                The decision record
              </Link>
            </li>
            <li>
              <Link href="/learn/decision-lifecycle" className="text-sm text-[var(--accent)] hover:underline">
                What a decision word means
              </Link>
            </li>
            <li>
              <Link href="/learn/simulation" className="text-sm text-[var(--accent)] hover:underline">
                Simulation and broker results
              </Link>
            </li>
          </ul>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-16 sm:px-6" aria-labelledby="pricing-faq">
          <h2 id="pricing-faq" className="mb-6 text-center text-2xl font-semibold tracking-tight">
            Pricing FAQ
          </h2>
          <PricingFaq />
        </section>
      </main>
      <PricingFooter />
    </div>
  );
}
