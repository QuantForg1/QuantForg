"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  Building2,
  CreditCard,
  Landmark,
  Lock,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import { BrandMark } from "@/components/brand/brand-logo";
import {
  PricingFooter,
  PricingHeader,
  pricingBtnPrimary,
  pricingBtnSecondary,
} from "@/components/pricing/marketing-chrome";

type MethodId = "card" | "bank" | "crypto" | "stripe" | "paypal";

const methods: {
  id: MethodId;
  label: string;
  hint: string;
  icon: typeof CreditCard;
}[] = [
  { id: "card", label: "Credit Card", hint: "Visa, Mastercard, Amex", icon: CreditCard },
  { id: "bank", label: "Bank Transfer", hint: "Wire / ACH instructions", icon: Landmark },
  { id: "crypto", label: "Crypto", hint: "Stablecoin settlement", icon: Wallet },
  { id: "stripe", label: "Stripe", hint: "Hosted Stripe Checkout", icon: CreditCard },
  { id: "paypal", label: "PayPal", hint: "PayPal checkout", icon: Building2 },
];

export default function PurchasePage() {
  const router = useRouter();
  const [method, setMethod] = useState<MethodId>("card");
  const [submitting, setSubmitting] = useState(false);

  return (
    <div className="min-h-screen overflow-x-clip">
      <PricingHeader active="purchase" />

      <main id="main-content" className="mx-auto w-full max-w-6xl px-4 pb-20 pt-6 sm:px-6" tabIndex={-1}>
        <div className="qf-fade-in mx-auto max-w-xl text-center">
          <p className="qf-label text-[var(--accent)]">Secure checkout</p>
          <h1 className="mt-3 font-[family-name:var(--font-display)] text-3xl tracking-tight sm:text-4xl">
            Complete your purchase
          </h1>
          <p className="mt-3 text-[var(--fg-muted)]">
            Institutional License · One-time payment · Account after success
          </p>
        </div>

        <div className="mx-auto mt-10 grid max-w-5xl gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          <section
            aria-labelledby="methods-heading"
            className="qf-glass-card p-6 sm:p-8"
          >
            <h2 id="methods-heading" className="text-base font-semibold tracking-tight">
              Payment method
            </h2>
            <p className="mt-1 text-sm text-[var(--fg-muted)]">
              Placeholders only — processor SDKs will mount here without changing this UX.
            </p>
            <fieldset className="mt-6 space-y-2.5">
              <legend className="sr-only">Select a payment method</legend>
              {methods.map((m) => {
                const Icon = m.icon;
                const selected = method === m.id;
                return (
                  <label
                    key={m.id}
                    className={`flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3.5 transition-all duration-[var(--duration-os)] ease-[var(--ease-os)] ${
                      selected
                        ? "border-[var(--accent)]/50 bg-[var(--accent-soft)] shadow-[var(--shadow-card)]"
                        : "border-[var(--border)] bg-[var(--bg-elevated)]/50 hover:border-[var(--border-strong)]"
                    }`}
                  >
                    <input
                      type="radio"
                      name="payment-method"
                      value={m.id}
                      checked={selected}
                      onChange={() => setMethod(m.id)}
                      className="mt-1 accent-[var(--accent)]"
                    />
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-2)] text-[var(--accent)]">
                      <Icon className="h-4 w-4" strokeWidth={1.75} aria-hidden />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-[var(--fg)]">{m.label}</span>
                      <span className="block text-xs text-[var(--fg-subtle)]">{m.hint}</span>
                    </span>
                  </label>
                );
              })}
            </fieldset>

            <div
              className="mt-6 rounded-xl border border-dashed border-[var(--border-strong)] bg-[var(--bg)]/50 px-4 py-5 text-sm text-[var(--fg-muted)]"
              role="status"
            >
              <p className="font-medium text-[var(--fg)]">Payment form placeholder</p>
              <p className="mt-1">
                Card fields and wallet redirects attach here. Demo checkout continues without
                charging.
              </p>
            </div>

            <ul className="mt-5 flex flex-wrap gap-3 text-xs text-[var(--fg-subtle)]">
              <li className="inline-flex items-center gap-1.5">
                <Lock className="h-3.5 w-3.5 text-[var(--accent)]" aria-hidden />
                Encrypted checkout path
              </li>
              <li className="inline-flex items-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-[var(--accent)]" aria-hidden />
                No recurring billing
              </li>
            </ul>

            <button
              type="button"
              className={`${pricingBtnPrimary} qf-btn-elevate mt-6 h-12 w-full text-base`}
              disabled={submitting}
              onClick={() => {
                setSubmitting(true);
                window.setTimeout(() => {
                  router.push(`/purchase/success?method=${encodeURIComponent(method)}`);
                }, 480);
              }}
            >
              {submitting ? "Processing…" : "Pay $2,499 — Lifetime Access"}
            </button>
          </section>

          <aside className="qf-glass-card h-fit border-[var(--accent)]/20 p-6 sm:p-8" aria-labelledby="order-heading">
            <div className="relative">
              <p className="qf-label text-[var(--accent)]">Order summary</p>
              <h2 id="order-heading" className="mt-2 text-lg font-semibold tracking-tight">
                Institutional License
              </h2>
              <span className="qf-lifetime-badge mt-4 inline-flex">
                <span className="qf-lifetime-badge__glow" aria-hidden />
                LIFETIME ACCESS
              </span>
              <p className="mt-5 font-[family-name:var(--font-display)] text-4xl font-semibold tracking-tight text-[var(--accent)]">
                $2,499
              </p>
              <p className="mt-1 text-sm text-[var(--fg-muted)]">
                Lifetime Access · One-Time Payment
              </p>
              <p className="mt-5 text-sm font-medium text-[var(--fg)]">What&apos;s Included</p>
              <ul className="mt-3 space-y-2 text-sm text-[var(--fg-muted)]">
                {[
                  "Everything Included",
                  "No Hidden Fees",
                  "One-Time Payment",
                  "Lifetime Access",
                  "Future Updates",
                ].map((line) => (
                  <li key={line} className="flex items-center gap-2">
                    <ShieldCheck className="h-3.5 w-3.5 text-[var(--accent)]" aria-hidden />
                    {line}
                  </li>
                ))}
              </ul>
              <div className="mt-6 flex items-center justify-between border-t border-[var(--border)] pt-4 text-sm">
                <span className="font-medium text-[var(--fg)]">Total due</span>
                <span className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight">
                  $2,499
                </span>
              </div>
              <BrandMark size={36} className="mt-6" />
              <Link href="/pricing" className={`${pricingBtnSecondary} mt-6 w-full`}>
                Back to pricing
              </Link>
            </div>
          </aside>
        </div>
      </main>

      <PricingFooter />
    </div>
  );
}
