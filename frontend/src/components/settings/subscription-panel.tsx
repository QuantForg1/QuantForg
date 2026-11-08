"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ANNUAL_BILLING_SUPPORTED,
  BILLING_PLANS,
  BILLING_PROVIDER,
  formatUsd,
} from "@/lib/billing/plans";
import { billingApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

/**
 * Subscription management — never invents paid status.
 * Entitlements come only from server billing/license state.
 */
export function SubscriptionPanel() {
  const qc = useQueryClient();
  const meQ = useQuery({
    queryKey: ["billing-me"],
    queryFn: () => billingApi.me(),
    retry: false,
    staleTime: 15_000,
  });
  const providerQ = useQuery({
    queryKey: ["billing-provider"],
    queryFn: () => billingApi.provider(),
    retry: false,
    staleTime: 60_000,
  });

  const cancelMut = useMutation({
    mutationFn: () => billingApi.cancel(),
    onSuccess: async (data) => {
      toast.success(str(asRecord(data).note, "Cancellation recorded"));
      await qc.invalidateQueries({ queryKey: ["billing-me"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Cancel failed"),
  });

  const me = asRecord(meQ.data);
  const provider = asRecord(providerQ.data || BILLING_PROVIDER);
  const subscription = asRecord(me.subscription);
  const license = asRecord(me.license);
  const orders = asList(me.orders).map(asRecord);
  const state = str(subscription.state, meQ.isLoading ? "loading" : "none");
  const configured = Boolean(provider.configured ?? BILLING_PROVIDER.configured);

  return (
    <div className="space-y-6">
      <div className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-5">
        <h3 className="text-base font-semibold">Current status</h3>
        <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">
          {configured
            ? "Crypto checkout uses NOWPayments LIVE. This screen reflects server-verified subscription and license state only."
            : "NOWPayments LIVE credentials are not configured on the API yet. Checkout will fail until Railway secrets are set."}
        </p>
        <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-[var(--fg-subtle)]">Subscription</dt>
            <dd className="font-medium capitalize">{state.replaceAll("_", " ")}</dd>
          </div>
          <div>
            <dt className="text-[var(--fg-subtle)]">Plan</dt>
            <dd className="font-medium">{str(subscription.plan_id, "—")}</dd>
          </div>
          <div>
            <dt className="text-[var(--fg-subtle)]">License</dt>
            <dd className="font-medium">
              {license.tier
                ? `${str(license.tier)} · ${str(license.status)}`
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-[var(--fg-subtle)]">Period end / grace</dt>
            <dd className="font-medium">
              {str(subscription.period_end || license.expires_at, "—")}
            </dd>
          </div>
        </dl>
        <p className="mt-3 text-sm text-[var(--fg-subtle)]">
          {str(provider.note, BILLING_PROVIDER.note)}
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            href="/billing/checkout?plan=professional"
            className="qf-btn-primary inline-flex h-10 items-center rounded-[var(--radius-sm)] px-4 text-sm font-semibold"
          >
            Pay with crypto
          </Link>
          <Link
            href="/pricing"
            className="inline-flex h-10 items-center rounded-[var(--radius-sm)] border border-[var(--border)] px-4 text-sm"
          >
            View plans
          </Link>
          {state === "active" ? (
            <Button
              variant="secondary"
              size="sm"
              disabled={cancelMut.isPending}
              onClick={() => cancelMut.mutate()}
            >
              Cancel renewal
            </Button>
          ) : null}
        </div>
      </div>

      <div>
        <h3 className="text-base font-semibold">Published plans</h3>
        {!ANNUAL_BILLING_SUPPORTED ? (
          <p className="mt-1 text-xs text-[var(--fg-subtle)]">
            Monthly pricing only — automatic recurring crypto is not enabled.
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
              <Link
                href={`/billing/checkout?plan=${plan.id}`}
                className="mt-3 inline-block text-xs text-[var(--accent)] underline"
              >
                Checkout
              </Link>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-[var(--radius-os)] border border-[var(--border)] p-5">
        <h3 className="text-base font-semibold">Payment history</h3>
        {meQ.isError ? (
          <p className="mt-2 text-sm text-[var(--fg-muted)]">
            Unable to load orders right now.
          </p>
        ) : orders.length === 0 ? (
          <p className="mt-2 text-sm text-[var(--fg-muted)]">
            No invoices yet. Completed LIVE payments appear here after verified IPN processing.
          </p>
        ) : (
          <ul className="mt-3 space-y-2 text-sm">
            {orders.map((o) => (
              <li
                key={str(o.order_code)}
                className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)]/60 py-2"
              >
                <span>
                  {str(o.plan_id)} · {str(o.order_code)}
                </span>
                <span className="tabular text-[var(--fg-muted)]">
                  {o.amount_usd != null ? formatUsd(Number(o.amount_usd)) : "—"} ·{" "}
                  {str(o.status)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
