"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  PricingFooter,
  PricingHeader,
  pricingBtnPrimary,
  pricingBtnSecondary,
} from "@/components/pricing/marketing-chrome";
import { billingApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import {
  formatBillingDate,
  formatUsd,
  PAYMENT_METHOD_LABEL,
} from "@/lib/billing/plans";
import { useAuth } from "@/providers/auth-provider";

function isUnpaid(status: string): boolean {
  return ["pending_payment", "confirming", "partially_paid", "renewal_due", "past_due"].includes(
    status,
  );
}

function isFailed(status: string): boolean {
  return status === "payment_failed";
}

export default function BillingInvoicesPage() {
  const { isAuthenticated, loading } = useAuth();
  const [invoices, setInvoices] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (loading) return;
      if (!isAuthenticated) {
        setInvoices([]);
        return;
      }
      setBusy(true);
      setError(null);
      try {
        const me = asRecord(await billingApi.me());
        if (!cancelled) {
          setInvoices(asList(me.invoices ?? me.orders).map(asRecord));
        }
      } catch {
        if (!cancelled) setError("Unable to load invoices right now.");
      } finally {
        if (!cancelled) setBusy(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, loading]);

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
        ) : busy ? (
          <p className="mt-8 text-sm text-[var(--fg-muted)]">Loading invoices…</p>
        ) : error ? (
          <p className="mt-8 text-sm text-[var(--danger)]" role="alert">
            {error}
          </p>
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
            {invoices.map((inv) => {
              const status = str(inv.status);
              const planId = str(inv.plan_id, "professional");
              const dueAt = formatBillingDate(
                str(inv.expires_at || inv.period_end || inv.created_at),
              );
              const invoiceUrl = str(inv.invoice_url, "");
              const checkoutHref = `/billing/checkout?plan=${encodeURIComponent(planId)}`;

              return (
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
                        {planId} · {PAYMENT_METHOD_LABEL}
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
                    Created {formatBillingDate(str(inv.created_at))}
                    {inv.paid_at ? ` · Paid ${formatBillingDate(str(inv.paid_at))}` : ""}
                    {!inv.paid_at ? ` · Due ${dueAt}` : ""}
                  </p>

                  {isUnpaid(status) ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {invoiceUrl ? (
                        <a
                          href={invoiceUrl}
                          className={`${pricingBtnPrimary} text-center text-sm`}
                        >
                          Continue {PAYMENT_METHOD_LABEL}
                        </a>
                      ) : null}
                      <Link href={checkoutHref} className={pricingBtnSecondary}>
                        Return to checkout
                      </Link>
                    </div>
                  ) : null}

                  {isFailed(status) ? (
                    <p
                      className="mt-3 rounded-[var(--radius-sm)] border border-[var(--danger)]/30 bg-[color-mix(in_srgb,var(--danger)_8%,transparent)] p-3 text-xs leading-relaxed text-[var(--fg-muted)]"
                      role="note"
                    >
                      This payment did not complete on the server. Your account was not upgraded.
                      Open checkout again or use a new invoice — access activates only after
                      QuantForg verifies a finished {PAYMENT_METHOD_LABEL}.
                      {inv.provider_status
                        ? ` Processor status: ${str(inv.provider_status)}.`
                        : ""}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </main>
      <PricingFooter />
    </div>
  );
}
