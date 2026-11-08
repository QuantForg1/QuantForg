"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { BrandMark } from "@/components/brand/brand-logo";
import {
  PricingFooter,
  PricingHeader,
  pricingBtnPrimary,
  pricingBtnSecondary,
} from "@/components/pricing/marketing-chrome";
import { billingApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asRecord, str } from "@/lib/desk";
import {
  BILLING_PROVIDER,
  formatUsd,
  getPlan,
  type PlanId,
} from "@/lib/billing/plans";
import { useAuth } from "@/providers/auth-provider";

function CheckoutInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { isAuthenticated, loading } = useAuth();
  const planId = (params.get("plan") || "professional") as PlanId;
  const plan = useMemo(() => getPlan(planId), [planId]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);

  async function startCheckout() {
    if (!plan || !accepted) return;
    setBusy(true);
    setError(null);
    try {
      const origin = window.location.origin;
      const result = asRecord(
        await billingApi.checkout({
          plan_id: plan.id,
          success_url: `${origin}/billing/return?status=return`,
          cancel_url: `${origin}/billing/return?status=cancel`,
        }),
      );
      const url = str(result.invoice_url);
      if (!url) {
        setError("Checkout did not return a payment URL. Credentials may be missing.");
        setBusy(false);
        return;
      }
      window.location.assign(url);
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.message || e.code || "Checkout failed"
          : "Checkout failed";
      setError(msg);
      setBusy(false);
    }
  }

  if (!plan) {
    return (
      <p className="text-center text-sm text-[var(--fg-muted)]">
        Unknown plan. <Link href="/pricing">Back to pricing</Link>
      </p>
    );
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div className="text-center">
        <BrandMark size={56} className="mx-auto" />
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight">
          Confirm subscription
        </h1>
        <p className="mt-2 text-sm text-[var(--fg-muted)]">
          Pay with cryptocurrency through NOWPayments LIVE. Access activates only after QuantForg
          verifies a finished payment notification.
        </p>
      </div>

      <article className="qf-glass-card space-y-3 p-6">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-lg font-semibold">{plan.name}</h2>
          <p className="text-xl font-semibold tabular text-[var(--accent)]">
            {formatUsd(plan.monthlyPriceUsd)}
            <span className="text-sm font-normal text-[var(--fg-subtle)]"> / mo</span>
          </p>
        </div>
        <p className="text-sm text-[var(--fg-muted)]">{plan.positioning}</p>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between gap-3">
            <dt className="text-[var(--fg-muted)]">Provider</dt>
            <dd className="font-medium">NOWPayments Crypto (LIVE)</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-[var(--fg-muted)]">Amount due</dt>
            <dd className="font-mono tabular">{formatUsd(plan.monthlyPriceUsd)} USD</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-[var(--fg-muted)]">License tier</dt>
            <dd className="font-medium">{plan.licenseTier}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-[var(--fg-muted)]">Renewal</dt>
            <dd className="font-medium">Manual invoice (no auto-charge)</dd>
          </div>
        </dl>
        <p className="text-xs leading-relaxed text-[var(--fg-subtle)]">{BILLING_PROVIDER.note}</p>
      </article>

      {!loading && !isAuthenticated ? (
        <div className="rounded-[var(--radius-os)] border border-[var(--border)] p-4 text-sm">
          <p className="text-[var(--fg-muted)]">Sign in to create a LIVE payment invoice.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              href={`/login?next=${encodeURIComponent(`/billing/checkout?plan=${plan.id}`)}`}
              className={pricingBtnPrimary}
            >
              Sign in
            </Link>
            <Link
              href={`/register?plan=${plan.id}`}
              className={pricingBtnSecondary}
            >
              Create account
            </Link>
          </div>
        </div>
      ) : (
        <>
          <label className="flex items-start gap-3 text-sm text-[var(--fg-muted)]">
            <input
              type="checkbox"
              className="mt-1"
              checked={accepted}
              onChange={(e) => setAccepted(e.target.checked)}
            />
            <span>
              I agree to the{" "}
              <Link href="/terms" className="text-[var(--accent)] underline">
                Terms
              </Link>
              ,{" "}
              <Link href="/privacy" className="text-[var(--accent)] underline">
                Privacy Policy
              </Link>
              , and{" "}
              <Link href="/risk-disclosure" className="text-[var(--accent)] underline">
                Risk Disclosure
              </Link>
              . I understand paid access is granted only after verified payment.
            </span>
          </label>
          {error ? (
            <p className="rounded-lg border border-[var(--danger)]/40 bg-[var(--danger-soft)] px-3 py-2 text-sm text-[var(--danger)]">
              {error}
            </p>
          ) : null}
          <button
            type="button"
            className={`${pricingBtnPrimary} w-full`}
            disabled={!accepted || busy || loading}
            onClick={() => {
              void startCheckout();
            }}
          >
            {busy ? "Creating LIVE invoice…" : "Continue to NOWPayments"}
          </button>
          <button
            type="button"
            className={`${pricingBtnSecondary} w-full`}
            onClick={() => router.push("/pricing")}
          >
            Back to plans
          </button>
        </>
      )}
    </div>
  );
}

export default function BillingCheckoutPage() {
  return (
    <div className="min-h-screen overflow-x-clip">
      <PricingHeader />
      <main id="main-content" className="mx-auto w-full max-w-6xl px-4 pb-20 pt-8 sm:px-6" tabIndex={-1}>
        <Suspense fallback={<p className="text-center text-sm text-[var(--fg-muted)]">Loading…</p>}>
          <CheckoutInner />
        </Suspense>
      </main>
      <PricingFooter />
    </div>
  );
}
