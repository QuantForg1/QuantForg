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
  PAYMENT_METHOD_LABEL,
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
    if (!plan || !accepted || busy) return;
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
      const url = str(result.invoice_url, "");
      if (!url || url === "—") {
        setError(
          "Checkout did not return a payment URL. Crypto Payment may be temporarily unavailable.",
        );
        setBusy(false);
        return;
      }
      window.location.assign(url);
    } catch (e) {
      let msg = "Checkout failed";
      if (e instanceof ApiError) {
        if (e.code === "UNKNOWN_PLAN") msg = "That plan is not available.";
        else if (e.code === "CRYPTO_INVOICE_FAILED" || e.code === "NOWPAYMENTS_INVOICE_FAILED")
          msg = "Unable to create a Crypto Payment invoice. Please retry in a moment.";
        else if (e.code === "NOWPAYMENTS_NOT_CONFIGURED" || e.status === 503)
          msg = "Crypto Payment is not available right now. Please try again later.";
        else if (e.status === 401) msg = "Your session expired. Sign in again to continue checkout.";
        else msg = e.message || e.code || msg;
      }
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

  const nextPath = `/billing/checkout?plan=${plan.id}`;

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div className="text-center">
        <BrandMark size={56} className="mx-auto" />
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight">
          Confirm subscription
        </h1>
        <p className="mt-2 text-sm text-[var(--fg-muted)]">
          Pay with {PAYMENT_METHOD_LABEL}. Access activates only after QuantForg verifies a
          completed payment — not from this page alone.
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
            <dt className="text-[var(--fg-muted)]">Payment method</dt>
            <dd className="font-medium">{PAYMENT_METHOD_LABEL}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-[var(--fg-muted)]">Amount due</dt>
            <dd className="font-mono tabular">{formatUsd(plan.monthlyPriceUsd)} USD</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-[var(--fg-muted)]">Billing</dt>
            <dd className="font-medium">Monthly · manual renewal invoice</dd>
          </div>
        </dl>
        <p className="text-xs leading-relaxed text-[var(--fg-subtle)]">{BILLING_PROVIDER.note}</p>
      </article>

      {!loading && !isAuthenticated ? (
        <div className="rounded-[var(--radius-os)] border border-[var(--border)] p-4 text-sm">
          <p className="text-[var(--fg-muted)]">
            Sign in to create a Crypto Payment invoice. Your selected plan will be preserved.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              href={`/login?next=${encodeURIComponent(nextPath)}`}
              className={pricingBtnPrimary}
            >
              Sign in
            </Link>
            <Link href={`/register?plan=${plan.id}`} className={pricingBtnSecondary}>
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
            <p
              className="rounded-lg border border-[var(--danger)]/40 bg-[var(--danger-soft)] px-3 py-2 text-sm text-[var(--danger)]"
              role="alert"
            >
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
            {busy ? "Creating payment invoice…" : `Continue with ${PAYMENT_METHOD_LABEL}`}
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
      <main
        id="main-content"
        className="mx-auto w-full max-w-6xl px-4 pb-20 pt-8 sm:px-6"
        tabIndex={-1}
      >
        <Suspense fallback={<p className="text-center text-sm text-[var(--fg-muted)]">Loading…</p>}>
          <CheckoutInner />
        </Suspense>
      </main>
      <PricingFooter />
    </div>
  );
}
