"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  PricingFooter,
  PricingHeader,
  pricingBtnPrimary,
  pricingBtnSecondary,
} from "@/components/pricing/marketing-chrome";
import { billingApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { formatUsd, PAYMENT_METHOD_LABEL } from "@/lib/billing/plans";
import { useAuth } from "@/providers/auth-provider";

export default function BillingInvoicesPage() {
  const { isAuthenticated, loading } = useAuth();
  const meQ = useQuery({
    queryKey: ["billing-me"],
    queryFn: () => billingApi.me(),
    enabled: isAuthenticated,
    retry: false,
  });
  const invoices = asList(asRecord(meQ.data).invoices ?? asRecord(meQ.data).orders).map(
    asRecord,
  );

  return (
    <div className="min-h-screen overflow-x-clip">
      <PricingHeader />
      <main
        id="main-content"
        className="mx-auto w-full max-w-3xl px-4 pb-20 pt-8 sm:px-6"
        tabIndex={-1}
      >
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight">
          Invoices
        </h1>
        <p className="mt-2 text-sm text-[var(--fg-muted)]">
          Crypto Payment invoices for your QuantForg subscription. Statuses come from the server —
          pending invoices are never shown as paid.
        </p>

        {!loading && !isAuthenticated ? (
          <div className="mt-8 rounded-[var(--radius-os)] border border-[var(--border)] p-5 text-sm">
            <p className="text-[var(--fg-muted)]">Sign in to view your invoices.</p>
            <Link
              href={`/login?next=${encodeURIComponent("/billing/invoices")}`}
              className={`${pricingBtnPrimary} mt-4`}
            >
              Sign in
            </Link>
          </div>
        ) : meQ.isLoading ? (
          <p className="mt-8 text-sm text-[var(--fg-muted)]">Loading invoices…</p>
        ) : invoices.length === 0 ? (
          <div className="mt-8 rounded-[var(--radius-os)] border border-[var(--border)] p-5 text-sm text-[var(--fg-muted)]">
            No invoices yet.
            <div className="mt-4 flex flex-wrap gap-2">
              <Link href="/pricing" className={pricingBtnPrimary}>
                View plans
              </Link>
              <Link href="/settings" className={pricingBtnSecondary}>
                Subscription settings
              </Link>
            </div>
          </div>
        ) : (
          <ul className="mt-8 space-y-3">
            {invoices.map((inv) => (
              <li
                key={str(inv.order_code)}
                className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <Link
                      href={`/billing/invoices/${encodeURIComponent(str(inv.order_code))}`}
                      className="font-medium text-[var(--accent)] underline"
                    >
                      {str(inv.invoice_number || inv.order_code)}
                    </Link>
                    <p className="mt-1 text-sm text-[var(--fg-muted)]">
                      {str(inv.plan_id)} · {PAYMENT_METHOD_LABEL}
                    </p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="font-semibold tabular text-[var(--fg)]">
                      {inv.amount_usd != null ? formatUsd(Number(inv.amount_usd)) : "—"}
                    </p>
                    <p className="text-[var(--fg-muted)]">
                      {str(inv.status_label || inv.status)}
                    </p>
                  </div>
                </div>
                <p className="mt-2 text-xs text-[var(--fg-subtle)]">
                  Created {str(inv.created_at, "—")}
                  {inv.paid_at ? ` · Paid ${str(inv.paid_at)}` : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </main>
      <PricingFooter />
    </div>
  );
}
