"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  PricingFooter,
  PricingHeader,
  pricingBtnPrimary,
  pricingBtnSecondary,
} from "@/components/pricing/marketing-chrome";
import { billingApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { PAYMENT_METHOD_LABEL } from "@/lib/billing/plans";
import { useAuth } from "@/providers/auth-provider";

function ReturnInner() {
  const params = useSearchParams();
  const status = params.get("status") || "return";
  const { isAuthenticated, loading } = useAuth();
  const [summary, setSummary] = useState<string>("Checking payment status…");
  const [orders, setOrders] = useState<Record<string, unknown>[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (loading) return;
      if (!isAuthenticated) {
        setSummary(
          `You returned from ${PAYMENT_METHOD_LABEL}. Sign in to see verified payment status from the server.`,
        );
        return;
      }
      try {
        const me = asRecord(await billingApi.me());
        const sub = asRecord(me.subscription);
        const list = asList(me.invoices ?? me.orders).map(asRecord);
        if (!cancelled) {
          setOrders(list.slice(0, 5));
          const state = str(sub.state, "none");
          if (state === "active") {
            setSummary(
              "Your subscription is active. Paid access was granted after a verified completed payment.",
            );
          } else if (state === "pending_payment" || state === "confirming") {
            setSummary(
              "Payment is still pending or confirming. This page does not grant access — wait for verified completion, then refresh.",
            );
          } else if (state === "trial") {
            setSummary("Your Starter trial is active. Upgrade anytime from Settings → Subscription.");
          } else {
            setSummary(
              "No active paid subscription yet. If you just paid, wait for confirmation, then refresh.",
            );
          }
        }
      } catch {
        if (!cancelled) {
          setSummary(
            "Unable to load billing status right now. Try Settings → Subscription shortly.",
          );
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, loading]);

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight">
        {status === "cancel" ? "Checkout cancelled" : "Payment return"}
      </h1>
      <p className="text-sm leading-relaxed text-[var(--fg-muted)]">{summary}</p>
      <p className="text-xs text-[var(--fg-subtle)]">
        A successful browser redirect is not proof of payment. QuantForg activates licenses only
        after the backend verifies a completed {PAYMENT_METHOD_LABEL}.
      </p>
      {orders.length > 0 ? (
        <ul className="space-y-2 rounded-[var(--radius-os)] border border-[var(--border)] p-4 text-sm">
          {orders.map((o) => (
            <li key={str(o.order_code)} className="flex justify-between gap-3">
              <span>
                {str(o.invoice_number || o.order_code)} · {str(o.plan_id)}
              </span>
              <span className="tabular text-[var(--fg-muted)]">
                {str(o.status_label || o.status)}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Link href="/settings" className={pricingBtnPrimary}>
          Open subscription settings
        </Link>
        <Link href="/billing/invoices" className={pricingBtnSecondary}>
          View invoices
        </Link>
        <Link href="/pricing" className={pricingBtnSecondary}>
          Pricing
        </Link>
      </div>
    </div>
  );
}

export default function BillingReturnPage() {
  return (
    <div className="min-h-screen overflow-x-clip">
      <PricingHeader />
      <main
        id="main-content"
        className="mx-auto w-full max-w-6xl px-4 pb-20 pt-8 sm:px-6"
        tabIndex={-1}
      >
        <Suspense fallback={<p className="text-sm text-[var(--fg-muted)]">Loading…</p>}>
          <ReturnInner />
        </Suspense>
      </main>
      <PricingFooter />
    </div>
  );
}
