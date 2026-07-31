"use client";

import Link from "next/link";
import { Suspense, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Check, CheckCircle2 } from "lucide-react";
import { BrandMark } from "@/components/brand/brand-logo";
import {
  PricingFooter,
  PricingHeader,
  pricingBtnPrimary,
  pricingBtnSecondary,
} from "@/components/pricing/marketing-chrome";
import { markLifetimePurchaseComplete } from "@/lib/licensing/purchase-gate";

const NEXT_STEPS = [
  "Complete your account",
  "Configure MT5",
  "Connect your broker",
  "Begin trading",
];

function SuccessBody() {
  const params = useSearchParams();
  const method = params.get("method") ?? "card";

  useEffect(() => {
    markLifetimePurchaseComplete();
  }, []);

  return (
    <div className="qf-fade-in qf-glass-card relative w-full overflow-hidden border-[var(--accent)]/25 p-8 text-center sm:p-12">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(0,212,224,0.2),transparent_55%)]"
        aria-hidden
      />
      <div className="relative">
        <div className="qf-success-ring qf-success-pulse mx-auto flex h-24 w-24 items-center justify-center rounded-full bg-[var(--accent-soft)] text-[var(--accent)]">
          <CheckCircle2 className="h-12 w-12" strokeWidth={1.4} aria-hidden />
        </div>
        <div className="mx-auto mt-7">
          <BrandMark size={64} priority />
        </div>
        <p className="qf-label mt-6 text-[var(--accent)]">Payment Successful</p>
        <h1 className="mt-3 font-[family-name:var(--font-display)] text-3xl tracking-tight sm:text-4xl">
          Welcome to QuantForg.
        </h1>
        <p className="mt-3 text-base text-[var(--fg-muted)] sm:text-lg">
          Your Institutional License is Ready.
        </p>

        <ol className="mx-auto mt-8 max-w-sm space-y-2.5 text-left">
          {NEXT_STEPS.map((step, i) => (
            <li
              key={step}
              className="flex items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)]/70 px-4 py-3 text-sm text-[var(--fg)]"
            >
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--accent-soft)] text-[var(--accent)]">
                <Check className="h-3.5 w-3.5" strokeWidth={2.5} aria-hidden />
              </span>
              <span>
                <span className="mr-2 text-xs text-[var(--fg-subtle)]">{i + 1}.</span>
                {step}
              </span>
            </li>
          ))}
        </ol>

        <p className="mt-5 text-xs text-[var(--fg-subtle)]">Method placeholder: {method}</p>

        <Link
          href="/register?licensed=1"
          className={`${pricingBtnPrimary} qf-btn-elevate mt-8 h-12 w-full text-base`}
        >
          Create Your Account
        </Link>
        <p className="mt-3 text-xs text-[var(--fg-subtle)]">
          Account creation is available only on this screen.
        </p>
        <Link href="/login" className={`${pricingBtnSecondary} mt-4 w-full`}>
          Already have an account? Sign in
        </Link>
      </div>
    </div>
  );
}

export default function PurchaseSuccessPage() {
  return (
    <div className="min-h-screen overflow-x-clip">
      <PricingHeader active="purchase" />

      <main
        id="main-content"
        className="mx-auto flex w-full max-w-xl flex-col items-center px-4 pb-24 pt-10 sm:px-6"
        tabIndex={-1}
      >
        <Suspense
          fallback={
            <div className="h-96 w-full animate-pulse rounded-2xl bg-[var(--surface)]" />
          }
        >
          <SuccessBody />
        </Suspense>
      </main>

      <PricingFooter />
    </div>
  );
}
