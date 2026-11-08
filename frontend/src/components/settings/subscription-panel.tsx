"use client";

import Link from "next/link";
import {
  ANNUAL_BILLING_SUPPORTED,
  BILLING_PLANS,
  BILLING_PROVIDER,
  formatUsd,
} from "@/lib/billing/plans";

/**
 * Honest subscription management surface.
 * Never invents paid status. Checkout is disabled until a provider + webhooks exist.
 */
export function SubscriptionPanel() {
  return (
    <div className="space-y-6">
      <div className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-5">
        <h3 className="text-base font-semibold">Current status</h3>
        <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">
          No self-serve billing portal is connected in this deployment. Paid plan changes require
          verified payment confirmation and server-side license activation. This screen will never
          mark you as paid from a browser click alone.
        </p>
        <p className="mt-3 text-sm text-[var(--fg-subtle)]">{BILLING_PROVIDER.note}</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            href="/pricing"
            className="qf-btn-primary inline-flex h-10 items-center rounded-[var(--radius-sm)] px-4 text-sm font-semibold"
          >
            View plans
          </Link>
          <Link
            href="/contact?topic=subscription"
            className="inline-flex h-10 items-center rounded-[var(--radius-sm)] border border-[var(--border)] px-4 text-sm"
          >
            Request plan change
          </Link>
        </div>
      </div>

      <div>
        <h3 className="text-base font-semibold">Published plans</h3>
        {!ANNUAL_BILLING_SUPPORTED ? (
          <p className="mt-1 text-xs text-[var(--fg-subtle)]">
            Monthly pricing only — annual billing is not enabled yet.
          </p>
        ) : null}
        <ul className="mt-4 grid gap-3 sm:grid-cols-3">
          {BILLING_PLANS.map((plan) => (
            <li
              key={plan.id}
              className="rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--bg-elevated)] p-4"
            >
              <p className="font-medium">{plan.name}</p>
              <p className="mt-1 text-sm text-[var(--accent)]">
                {formatUsd(plan.monthlyPriceUsd)}
                <span className="text-[var(--fg-subtle)]"> / mo</span>
              </p>
              <p className="mt-2 text-xs leading-relaxed text-[var(--fg-muted)]">
                {plan.positioning}
              </p>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-[var(--radius-os)] border border-[var(--border)] p-5">
        <h3 className="text-base font-semibold">Billing history</h3>
        <p className="mt-2 text-sm text-[var(--fg-muted)]">
          Invoice history appears here after a recurring payment provider is connected and
          verified webhooks record entitlements. Until then, contact support for receipts from
          manually provisioned licenses.
        </p>
      </div>
    </div>
  );
}
