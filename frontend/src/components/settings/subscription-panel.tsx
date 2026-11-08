"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ANNUAL_BILLING_SUPPORTED,
  BILLING_PLANS,
  BILLING_PROVIDER,
  formatBillingDate,
  formatUsd,
  PAYMENT_METHOD_LABEL,
  PLAN_COMPARISON_ROWS,
  TRIAL_DAYS,
  TRIAL_EXPIRES_BEHAVIOR,
  TRIAL_FEATURES,
  TRIAL_POSITIONING,
} from "@/lib/billing/plans";
import { billingApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

function unpaidInvoiceStatuses(status: string): boolean {
  return ["pending_payment", "confirming", "partially_paid"].includes(status);
}

/**
 * Subscription management — never invents paid status.
 * Entitlements come only from server billing/license state (`billingApi.me`).
 */
export function SubscriptionPanel() {
  const qc = useQueryClient();
  const meQ = useQuery({
    queryKey: ["billing-me"],
    queryFn: () => billingApi.me(),
    retry: false,
    staleTime: 15_000,
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

  const trialMut = useMutation({
    mutationFn: () => billingApi.startTrial(),
    onSuccess: async () => {
      toast.success(`Your ${TRIAL_DAYS}-day Starter trial is active`);
      await qc.invalidateQueries({ queryKey: ["billing-me"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Unable to start trial"),
  });

  const me = asRecord(meQ.data);
  const provider = asRecord(me.provider || BILLING_PROVIDER);
  const subscription = asRecord(me.subscription);
  const license = asRecord(me.license);
  const trial = asRecord(me.trial);
  const invoices = asList(me.invoices ?? me.orders).map(asRecord);
  const state = str(subscription.state, meQ.isLoading ? "loading" : "none");
  const configured = Boolean(
    provider.configured ?? BILLING_PROVIDER.configured,
  );
  const paymentLabel = str(
    me.payment_method_label ||
      subscription.payment_method_label ||
      provider.payment_method_label,
    PAYMENT_METHOD_LABEL,
  );
  const subscriptionType = str(subscription.subscription_type, "—");
  const daysRemaining = num(
    trial.days_remaining ?? subscription.days_remaining,
    0,
  );
  const trialActive = state === "trial" || str(trial.status) === "active";
  const trialExpired = state === "trial_expired" || str(trial.status) === "expired";
  const canStartTrial = state === "none" && !trial.status;
  const graceDays = num(subscription.grace_days, 0);

  const planDisplay = trialActive
    ? str(trial.plan_name, "Starter Trial")
    : str(subscription.plan_name || subscription.plan_id, "—");

  const handleCancel = () => {
    const confirmed = window.confirm(
      "Cancel renewal? Your access continues until the current period ends. QuantForg does not auto-charge crypto — you will need a new invoice to renew later.",
    );
    if (confirmed) cancelMut.mutate();
  };

  return (
    <div className="space-y-6">
      <div className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-5">
        <h3 className="text-base font-semibold">Subscription dashboard</h3>
        <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">
          {configured
            ? `${paymentLabel} is available. This screen reflects server-verified subscription and license state only.`
            : `${paymentLabel} is not configured on the API yet. Checkout will fail until production credentials are set.`}
        </p>

        {trialActive ? (
          <div className="mt-4 rounded-[var(--radius-sm)] border border-[var(--accent)]/30 bg-[color-mix(in_srgb,var(--accent)_8%,transparent)] p-4">
            <p className="text-sm font-semibold text-[var(--accent)]">
              Your {TRIAL_DAYS}-day Starter trial is active.
            </p>
            <p className="mt-1 text-sm text-[var(--fg-muted)]">
              {daysRemaining} day{daysRemaining === 1 ? "" : "s"} remaining · ends{" "}
              {formatBillingDate(
                str(trial.expires_at || subscription.trial_expires_at || subscription.period_end),
              )}
            </p>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--surface-2)]">
              <div
                className="h-full rounded-full bg-[var(--accent)] transition-all"
                style={{
                  width: `${Math.max(4, Math.min(100, (daysRemaining / TRIAL_DAYS) * 100))}%`,
                }}
              />
            </div>
          </div>
        ) : null}

        {trialExpired ? (
          <div className="mt-4 rounded-[var(--radius-sm)] border border-[var(--warning)]/40 p-4 text-sm text-[var(--fg-muted)]">
            Your Starter trial has ended. Choose a plan and pay with {paymentLabel} to continue
            paid features. Your account and history are preserved.
          </div>
        ) : null}

        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-[var(--fg-subtle)]">Status</dt>
            <dd className="font-medium capitalize">{state.replaceAll("_", " ")}</dd>
          </div>
          <div>
            <dt className="text-[var(--fg-subtle)]">Plan</dt>
            <dd className="font-medium">{planDisplay}</dd>
          </div>
          <div>
            <dt className="text-[var(--fg-subtle)]">Subscription type</dt>
            <dd className="font-medium capitalize">
              {subscriptionType.replaceAll("_", " ")}
            </dd>
          </div>
          <div>
            <dt className="text-[var(--fg-subtle)]">Payment method</dt>
            <dd className="font-medium">{paymentLabel}</dd>
          </div>
          <div>
            <dt className="text-[var(--fg-subtle)]">Trial started</dt>
            <dd className="font-medium">
              {formatBillingDate(
                str(trial.started_at || subscription.trial_started_at),
              )}
            </dd>
          </div>
          <div>
            <dt className="text-[var(--fg-subtle)]">Trial ends</dt>
            <dd className="font-medium">
              {formatBillingDate(
                str(trial.expires_at || subscription.trial_expires_at),
              )}
            </dd>
          </div>
          <div>
            <dt className="text-[var(--fg-subtle)]">Activated</dt>
            <dd className="font-medium">
              {formatBillingDate(
                str(subscription.activated_at || license.issued_at),
              )}
            </dd>
          </div>
          <div>
            <dt className="text-[var(--fg-subtle)]">Next renewal due</dt>
            <dd className="font-medium">
              {formatBillingDate(str(subscription.next_renewal_due))}
            </dd>
          </div>
          <div>
            <dt className="text-[var(--fg-subtle)]">Current period end</dt>
            <dd className="font-medium">
              {formatBillingDate(
                str(subscription.period_end || subscription.access_until),
              )}
            </dd>
          </div>
          <div>
            <dt className="text-[var(--fg-subtle)]">Grace period end</dt>
            <dd className="font-medium">
              {formatBillingDate(str(subscription.grace_ends_at))}
              {graceDays > 0 ? (
                <span className="text-[var(--fg-subtle)]"> · {graceDays} day window</span>
              ) : null}
            </dd>
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
            <dt className="text-[var(--fg-subtle)]">License expires</dt>
            <dd className="font-medium">
              {formatBillingDate(str(license.expires_at))}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-[var(--fg-subtle)]">Billing</dt>
            <dd className="font-medium">
              {str(subscription.billing_frequency, "Monthly invoice")}
            </dd>
          </div>
        </dl>

        {str(subscription.renewal_instructions, "") ? (
          <p className="mt-4 text-xs leading-relaxed text-[var(--fg-subtle)]">
            {str(subscription.renewal_instructions)}
          </p>
        ) : null}

        <div className="mt-4 flex flex-wrap gap-3">
          {canStartTrial ? (
            <Button
              className="qf-btn-primary"
              size="sm"
              disabled={trialMut.isPending}
              onClick={() => trialMut.mutate()}
            >
              {trialMut.isPending
                ? "Starting trial…"
                : `Start ${TRIAL_DAYS}-day free trial`}
            </Button>
          ) : null}
          <Link
            href="/billing/checkout?plan=professional"
            className="qf-btn-primary inline-flex h-10 items-center rounded-[var(--radius-sm)] px-4 text-sm font-semibold"
          >
            {trialActive || trialExpired || state === "none"
              ? `Subscribe with ${paymentLabel}`
              : "Upgrade / renew"}
          </Link>
          <Link
            href="/pricing"
            className="inline-flex h-10 items-center rounded-[var(--radius-sm)] border border-[var(--border)] px-4 text-sm"
          >
            View plans
          </Link>
          <Link
            href="/billing/invoices"
            className="inline-flex h-10 items-center rounded-[var(--radius-sm)] border border-[var(--border)] px-4 text-sm"
          >
            Invoices
          </Link>
          {state === "active" ? (
            <Button
              variant="secondary"
              size="sm"
              disabled={cancelMut.isPending}
              onClick={handleCancel}
            >
              Cancel renewal
            </Button>
          ) : null}
          {state === "pending_payment" && str(subscription.invoice_url, "") ? (
            <a
              href={str(subscription.invoice_url)}
              className="inline-flex h-10 items-center rounded-[var(--radius-sm)] border border-[var(--accent)] px-4 text-sm text-[var(--accent)]"
            >
              Continue payment
            </a>
          ) : null}
        </div>
      </div>

      <div>
        <h3 className="text-base font-semibold">Published plans</h3>
        {!ANNUAL_BILLING_SUPPORTED ? (
          <p className="mt-1 text-xs text-[var(--fg-subtle)]">
            Monthly pricing only — automatic recurring crypto charging is not enabled.
          </p>
        ) : null}
        <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <li className="rounded-[var(--radius-sm)] border border-[var(--accent)]/40 bg-[color-mix(in_srgb,var(--accent)_6%,transparent)] p-4">
            <p className="font-medium">Free Trial</p>
            <p className="mt-1 text-sm text-[var(--accent)]">
              $0
              <span className="text-[var(--fg-subtle)]"> · {TRIAL_DAYS} days</span>
            </p>
            <p className="mt-2 text-xs leading-relaxed text-[var(--fg-muted)]">
              {TRIAL_POSITIONING}
            </p>
            <ul className="mt-3 space-y-1 text-xs text-[var(--fg-muted)]">
              {TRIAL_FEATURES.slice(0, 4).map((item) => (
                <li key={item}>· {item}</li>
              ))}
            </ul>
            {canStartTrial ? (
              <Button
                className="mt-3 w-full"
                size="sm"
                variant="secondary"
                disabled={trialMut.isPending}
                onClick={() => trialMut.mutate()}
              >
                Start trial
              </Button>
            ) : (
              <p className="mt-3 text-xs text-[var(--fg-subtle)]">{TRIAL_EXPIRES_BEHAVIOR}</p>
            )}
          </li>
          {BILLING_PLANS.map((plan) => (
            <li
              key={plan.id}
              className={`rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--bg-elevated)] p-4 ${
                plan.highlighted ? "ring-1 ring-[var(--accent)]/50" : ""
              }`}
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
                Checkout with {paymentLabel}
              </Link>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-[var(--radius-os)] border border-[var(--border)] p-5">
        <h3 className="text-base font-semibold">Plan comparison</h3>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-left text-xs">
            <thead className="bg-[var(--surface)]">
              <tr>
                <th className="px-3 py-2 font-medium">Capability</th>
                <th className="px-3 py-2 font-medium">Free Trial</th>
                <th className="px-3 py-2 font-medium">Starter</th>
                <th className="px-3 py-2 font-medium">Professional</th>
                <th className="px-3 py-2 font-medium">Premium</th>
              </tr>
            </thead>
            <tbody>
              {PLAN_COMPARISON_ROWS.map((row) => (
                <tr key={row.feature} className="border-t border-[var(--border)]">
                  <th scope="row" className="px-3 py-2 font-medium text-[var(--fg)]">
                    {row.feature}
                  </th>
                  <td className="px-3 py-2 text-[var(--fg-muted)]">{row.trial}</td>
                  <td className="px-3 py-2 text-[var(--fg-muted)]">{row.starter}</td>
                  <td className="px-3 py-2 text-[var(--fg-muted)]">{row.professional}</td>
                  <td className="px-3 py-2 text-[var(--fg-muted)]">{row.premium}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-[var(--radius-os)] border border-[var(--border)] p-5">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-base font-semibold">Invoices</h3>
          <Link href="/billing/invoices" className="text-xs text-[var(--accent)] underline">
            View all
          </Link>
        </div>
        {meQ.isError ? (
          <p className="mt-2 text-sm text-[var(--fg-muted)]">
            Unable to load invoices right now.
          </p>
        ) : invoices.length === 0 ? (
          <p className="mt-2 text-sm text-[var(--fg-muted)]">
            No invoices yet. Completed Crypto Payments appear here after verified processing.
          </p>
        ) : (
          <ul className="mt-3 space-y-2 text-sm">
            {invoices.slice(0, 8).map((o) => {
              const status = str(o.status);
              const due = formatBillingDate(
                str(o.expires_at || o.period_end || o.created_at),
              );
              return (
                <li
                  key={str(o.order_code)}
                  className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)]/60 py-2"
                >
                  <div>
                    <Link
                      href={`/billing/invoices/${encodeURIComponent(str(o.order_code))}`}
                      className="text-[var(--accent)] underline"
                    >
                      {str(o.invoice_number || o.order_code)} · {str(o.plan_id)}
                    </Link>
                    <p className="text-xs text-[var(--fg-subtle)]">
                      Due / period end {due}
                      {unpaidInvoiceStatuses(status)
                        ? ` · Pay with ${paymentLabel}`
                        : ""}
                    </p>
                  </div>
                  <span className="tabular text-[var(--fg-muted)]">
                    {o.amount_usd != null ? formatUsd(Number(o.amount_usd)) : "—"} ·{" "}
                    {str(o.status_label || o.status)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
