"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  PricingFooter,
  PricingHeader,
  pricingBtnPrimary,
  pricingBtnSecondary,
} from "@/components/pricing/marketing-chrome";
import { BrandMark } from "@/components/brand/brand-logo";
import { billingApi } from "@/lib/api/endpoints";
import { asRecord, str } from "@/lib/desk";
import { formatUsd, PAYMENT_METHOD_LABEL } from "@/lib/billing/plans";
import { useAuth } from "@/providers/auth-provider";

export default function BillingInvoiceDetailPage() {
  const params = useParams();
  const orderCode = String(params.orderCode || "");
  const { isAuthenticated, loading } = useAuth();
  const invQ = useQuery({
    queryKey: ["billing-invoice", orderCode],
    queryFn: () => billingApi.invoice(orderCode),
    enabled: isAuthenticated && Boolean(orderCode),
    retry: false,
  });
  const invoice = asRecord(asRecord(invQ.data).invoice);

  return (
    <div className="min-h-screen overflow-x-clip">
      <PricingHeader />
      <main
        id="main-content"
        className="mx-auto w-full max-w-2xl px-4 pb-20 pt-8 sm:px-6"
        tabIndex={-1}
      >
        {!loading && !isAuthenticated ? (
          <p className="text-sm text-[var(--fg-muted)]">
            Sign in to view this invoice.{" "}
            <Link
              href={`/login?next=${encodeURIComponent(`/billing/invoices/${orderCode}`)}`}
              className="text-[var(--accent)] underline"
            >
              Sign in
            </Link>
          </p>
        ) : invQ.isLoading ? (
          <p className="text-sm text-[var(--fg-muted)]">Loading invoice…</p>
        ) : invQ.isError || !invoice.order_code ? (
          <p className="text-sm text-[var(--danger)]">
            Invoice not found or you do not have access.
          </p>
        ) : (
          <article className="qf-glass-card space-y-5 p-6 print:border print:shadow-none">
            <div className="flex items-start justify-between gap-4">
              <div>
                <BrandMark size={48} />
                <h1 className="mt-3 text-2xl font-semibold tracking-tight">Invoice</h1>
                <p className="text-sm text-[var(--fg-muted)]">
                  {str(invoice.invoice_number || invoice.order_code)}
                </p>
              </div>
              <p className="rounded-full border border-[var(--border)] px-3 py-1 text-xs font-medium">
                {str(invoice.status_label || invoice.status)}
              </p>
            </div>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-[var(--fg-subtle)]">Plan</dt>
                <dd className="font-medium capitalize">{str(invoice.plan_id)}</dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Amount</dt>
                <dd className="font-mono tabular">
                  {invoice.amount_usd != null
                    ? `${formatUsd(Number(invoice.amount_usd))} ${str(invoice.currency, "USD").toUpperCase()}`
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Payment method</dt>
                <dd className="font-medium">{PAYMENT_METHOD_LABEL}</dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Created</dt>
                <dd className="font-medium">{str(invoice.created_at, "—")}</dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Paid at</dt>
                <dd className="font-medium">{str(invoice.paid_at, "—")}</dd>
              </div>
              <div>
                <dt className="text-[var(--fg-subtle)]">Period</dt>
                <dd className="font-medium">
                  {str(invoice.period_start, "—")} → {str(invoice.period_end, "—")}
                </dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-[var(--fg-subtle)]">Transaction reference</dt>
                <dd className="font-mono text-xs">
                  {str(invoice.provider_payment_id || invoice.provider_invoice_id, "—")}
                </dd>
              </div>
            </dl>
            {str(invoice.status) === "pending_payment" && str(invoice.invoice_url, "") ? (
              <a href={str(invoice.invoice_url)} className={`${pricingBtnPrimary} w-full`}>
                Continue with {PAYMENT_METHOD_LABEL}
              </a>
            ) : null}
            <div className="flex flex-wrap gap-2 print:hidden">
              <button type="button" className={pricingBtnSecondary} onClick={() => window.print()}>
                Print
              </button>
              <Link href="/billing/invoices" className={pricingBtnSecondary}>
                All invoices
              </Link>
              <Link href="/settings" className={pricingBtnSecondary}>
                Subscription
              </Link>
            </div>
          </article>
        )}
      </main>
      <PricingFooter />
    </div>
  );
}
