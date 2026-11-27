"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CreditCard, Crown, History, Receipt } from "lucide-react";
import {
  BILLING_PROVIDER,
  formatBillingDate,
  formatUsd,
  getPlan,
  PAYMENT_METHOD_LABEL,
} from "@/lib/billing/plans";
import { billingApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const PAYABLE = ["pending_payment", "confirming", "partially_paid", "renewal_due", "past_due"];

function daysUntil(iso: string): number | null {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return null;
  return Math.ceil((t - Date.now()) / 86_400_000);
}

type StatusView = { label: string; detail: string; live: boolean };

/** One clear status from server billing state. Never invents a paid plan. */
function subscriptionStatusView(state: string, robotAllowed: boolean): StatusView {
  switch (state) {
    case "active":
      return {
        label: "Active · Paid",
        detail: "Your plan is paid. The robot may trade under your risk profile.",
        live: true,
      };
    case "cancelled":
      return {
        label: robotAllowed ? "Cancelled · active until period end" : "Cancelled",
        detail:
          "Renewal is cancelled. The robot keeps working until the paid period ends, then stops opening new trades.",
        live: robotAllowed,
      };
    case "pending_payment":
      return {
        label: "Payment pending",
        detail:
          "Your invoice is waiting for payment or confirmation. The robot starts as soon as the payment is verified.",
        live: false,
      };
    case "grace":
    case "past_due":
    case "renewal_due":
      return {
        label: "Renewal due",
        detail:
          "Your paid period has ended or is about to end. Pay the new invoice now to keep the robot trading without interruption.",
        live: robotAllowed,
      };
    case "expired":
    case "payment_failed":
    case "suspended":
      return {
        label: state === "expired" ? "Expired" : "Payment required",
        detail:
          "Your subscription is not active. The robot does not open new trades; open positions stay protected. Renew to continue.",
        live: false,
      };
    case "loading":
      return { label: "Checking…", detail: "Reading your billing status.", live: false };
    default:
      return robotAllowed
        ? {
            label: "Active",
            detail: "The robot may trade under your risk profile.",
            live: true,
          }
        : {
            label: "No subscription",
            detail:
              "Your broker can be connected and verified for free. Choose a plan to start the robot.",
            live: false,
          };
  }
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

  const me = asRecord(meQ.data);
  const provider = asRecord(me.provider || BILLING_PROVIDER);
  const subscription = asRecord(me.subscription);
  const license = asRecord(me.license);
  const robotAccess = asRecord(me.robot_access);
  const invoices = asList(me.invoices ?? me.orders).map(asRecord);
  const state = str(subscription.state, meQ.isLoading ? "loading" : "none");
  const configured = Boolean(provider.configured ?? BILLING_PROVIDER.configured);
  const paymentLabel = str(
    me.payment_method_label ||
      subscription.payment_method_label ||
      provider.payment_method_label,
    PAYMENT_METHOD_LABEL,
  );
  const robotAllowed = robotAccess.allowed === true;
  const statusView = subscriptionStatusView(state, robotAllowed);
  const planKey = str(subscription.plan_id || license.tier, "");
  const catalog = getPlan(planKey) ?? (planKey === "enterprise" ? getPlan("premium") : undefined);
  const planDisplay = str(subscription.plan_name || subscription.plan_id, "");
  const amountNumber = num(
    subscription.amount_usd ?? subscription.price_usd ?? subscription.monthly_price_usd,
    NaN,
  );
  const amountLabel = Number.isFinite(amountNumber)
    ? formatUsd(amountNumber)
    : catalog && (state === "active" || state === "pending_payment" || state === "grace" || state === "cancelled")
      ? formatUsd(catalog.monthlyPriceUsd)
      : "Not available";
  const cycleRaw = str(subscription.billing_frequency || subscription.interval, "");
  const billingCycle = cycleRaw
    ? cycleRaw.replaceAll("_", " ")
    : state === "none" || state === "loading"
      ? "Not available"
      : "Monthly";
  const nextBilling = formatBillingDate(
    str(subscription.next_renewal_due || subscription.period_end || subscription.access_until),
  );
  const nextRaw = str(subscription.next_renewal_due || subscription.period_end || subscription.access_until);
  const daysLeft = daysUntil(nextRaw);
  const hasPlan = ["active", "cancelled", "grace", "past_due", "renewal_due", "pending_payment"].includes(state) && Boolean(planDisplay);
  const payableInvoice = invoices.find(
    (r) => PAYABLE.includes(str(r.status).toLowerCase()) && str(r.invoice_url, "") !== "",
  );
  const payUrl = str(payableInvoice?.invoice_url, "") || str(subscription.invoice_url, "");
  const renewSoon = state === "active" && daysLeft !== null && daysLeft <= 7;
  const renewHref = `/billing/checkout?plan=${encodeURIComponent(planKey || "professional")}`;
  const planCopy =
    catalog?.positioning ||
    statusView.detail ||
    (state === "none" || state === "loading"
      ? "No paid plan is active on this account."
      : "Plan details come from the billing service.");
  const highlights = catalog ? catalog.entitlements.slice(0, 4) : [];

  const handleCancel = () => {
    const confirmed = window.confirm(
      "Cancel renewal? Your access continues until the current period ends. QuantForg does not auto-charge crypto — you will need a new invoice to renew later.",
    );
    if (confirmed) cancelMut.mutate();
  };

  return (
    <div className="grid grid-cols-1 items-stretch gap-4 lg:grid-cols-2">
      <SubCard
        icon={<Crown className="h-4 w-4" aria-hidden />}
        title="Your Subscription"
        description="Current plan and subscription status."
      >
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-2xl font-semibold tracking-tight text-[var(--fg)]">
              {meQ.isLoading ? "Loading" : planDisplay || "No plan"}
            </p>
            <p className="mt-1 text-sm leading-relaxed text-[var(--fg-muted)]">{planCopy}</p>
          </div>
          <span
            data-testid="subscription-status-badge"
            className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${
              statusView.live
                ? "bg-[var(--success-soft)] text-[var(--success)]"
                : "bg-[var(--surface-2)] text-[var(--fg-muted)]"
            }`}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
            {statusView.label}
          </span>
        </div>
        {payUrl && (state === "pending_payment" || PAYABLE.includes(state)) ? (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--accent)]/40 bg-[var(--accent-soft)] px-3.5 py-3">
            <p className="text-sm text-[var(--fg)]">Your invoice is waiting for payment.</p>
            <a
              href={payUrl}
              className="inline-flex h-9 items-center rounded-full bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-fg)]"
            >
              Pay now
            </a>
          </div>
        ) : null}
        {!hasPlan && !meQ.isLoading ? (
          <div className="mt-4 rounded-xl border border-dashed border-[var(--border)] bg-[var(--bg)] px-4 py-5 text-center">
            <p className="text-sm font-semibold text-[var(--fg)]">You do not have an active plan</p>
            <p className="mt-1 text-xs leading-relaxed text-[var(--fg-muted)]">
              Your broker stays connected. Subscribe to switch the robot on.
            </p>
            <Link
              href="/pricing"
              className="mt-3 inline-flex h-10 items-center justify-center rounded-full bg-[var(--accent)] px-5 text-sm font-semibold text-[var(--accent-fg)]"
            >
              Subscribe now
            </Link>
          </div>
        ) : null}
        <p
          data-testid="robot-access"
          className="mt-4 text-sm leading-relaxed text-[var(--fg-muted)]"
        >
          Robot access: {meQ.isLoading ? "Checking…" : robotAllowed ? "Active" : "Subscription required"}.{" "}
          {statusView.detail}
        </p>
        {highlights.length > 0 ? (
          <ul className="mt-4 grid grid-cols-2 gap-2">
            {highlights.map((item) => (
              <li
                key={item}
                className="rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-xs text-[var(--fg-muted)]"
              >
                {item}
              </li>
            ))}
          </ul>
        ) : null}
        {!configured ? (
          <p className="mt-4 text-xs text-[var(--fg-subtle)]">
            {paymentLabel} is not configured on the API yet.
          </p>
        ) : null}
      </SubCard>

      <SubCard
        icon={<Receipt className="h-4 w-4" aria-hidden />}
        title="Subscription Details"
        description="Plan, billing cycle, next billing date, and amount."
      >
        <DetailRow label="Plan" value={meQ.isLoading ? "Loading" : planDisplay || "No plan"} />
        <DetailRow label="Status" value={statusView.label} live={statusView.live} />
        <DetailRow label="Billing Cycle" value={billingCycle} />
        <DetailRow
          label="Next Billing Date"
          value={
            nextBilling === "—"
              ? hasPlan
                ? "Pending payment"
                : "No plan"
              : daysLeft !== null && daysLeft >= 0
                ? `${nextBilling} · ${daysLeft} day${daysLeft === 1 ? "" : "s"} left`
                : nextBilling
          }
        />
        <DetailRow label="Amount" value={amountLabel === "Not available" ? "—" : amountLabel} />
        {hasPlan && state !== "cancelled" ? (
          <p className="mt-3 text-xs leading-relaxed text-[var(--fg-subtle)]">
            Crypto is not charged automatically. Pay the renewal invoice before the date above to avoid interruption.
          </p>
        ) : null}
      </SubCard>

      <SubCard
        icon={<CreditCard className="h-4 w-4" aria-hidden />}
        title="Manage Subscription"
        description="Pay, renew or change your plan."
      >
        <div className="flex flex-1 flex-col justify-end gap-3">
          {payUrl ? (
            <a
              href={payUrl}
              className="inline-flex h-11 items-center justify-center rounded-full bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-fg)]"
            >
              Pay invoice
            </a>
          ) : !hasPlan ? (
            <Link
              href="/pricing"
              className="inline-flex h-11 items-center justify-center rounded-full bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-fg)]"
            >
              Subscribe now
            </Link>
          ) : renewSoon || state === "grace" || state === "expired" ? (
            <Link
              href={renewHref}
              className="inline-flex h-11 items-center justify-center rounded-full bg-[var(--accent)] px-4 text-sm font-semibold text-[var(--accent-fg)]"
            >
              Renew now
            </Link>
          ) : null}
          {hasPlan ? (
            <Link
              href="/pricing"
              className={`inline-flex h-11 items-center justify-center rounded-full px-4 text-sm font-semibold ${
                payUrl || renewSoon ? "border border-[var(--border)] bg-[var(--bg)] text-[var(--fg)]" : "bg-[var(--accent)] text-[var(--accent-fg)]"
              }`}
            >
              Change plan
            </Link>
          ) : null}
          <Link
            href="/billing/invoices"
            className="inline-flex h-11 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--bg)] px-4 text-sm font-semibold text-[var(--fg)]"
          >
            View invoices
          </Link>
          {state === "active" || state === "cancelled" ? (
            <Button
              type="button"
              variant="secondary"
              disabled={cancelMut.isPending || state === "cancelled"}
              onClick={handleCancel}
            >
              {cancelMut.isPending ? "Cancelling…" : state === "cancelled" ? "Renewal cancelled" : "Cancel renewal"}
            </Button>
          ) : null}
        </div>
      </SubCard>

      <SubCard
        icon={<History className="h-4 w-4" aria-hidden />}
        title="Billing History"
        description="Payments recorded by the billing service."
        action={
          <Link href="/billing/invoices" className="text-xs font-semibold text-[var(--accent)]">
            View all
          </Link>
        }
      >
        {meQ.isError ? (
          <p className="text-sm text-[var(--fg-muted)]">Unable to load payment history.</p>
        ) : invoices.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">
            No payments yet. A row appears here after the billing service records one.
          </p>
        ) : (
          <div className="min-w-0 overflow-x-auto">
            <table className="w-full min-w-[32rem] text-left text-sm">
              <thead>
                <tr className="text-xs text-[var(--fg-subtle)]">
                  <th className="pb-2 font-medium">Date</th>
                  <th className="pb-2 font-medium">Description</th>
                  <th className="pb-2 font-medium">Amount</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 text-right font-medium">
                    <span className="sr-only">Action</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {invoices.slice(0, 6).map((row) => {
                  const status = str(row.status_label || row.status, "—");
                  const paid = ["finished", "paid", "confirmed", "complete"].includes(
                    str(row.status).toLowerCase(),
                  );
                  const payable = PAYABLE.includes(str(row.status).toLowerCase());
                  const rowPay = str(row.invoice_url, "");
                  const detailHref = `/billing/invoices/${encodeURIComponent(str(row.order_code))}`;
                  return (
                    <tr key={str(row.order_code || row.id)} className="border-t border-[var(--border)]">
                      <td className="py-2 pr-3 text-[var(--fg-muted)]">
                        {formatBillingDate(str(row.created_at || row.paid_at || row.expires_at))}
                      </td>
                      <td className="py-2 pr-3">
                        <Link
                          href={`/billing/invoices/${encodeURIComponent(str(row.order_code))}`}
                          className="text-[var(--fg)]"
                        >
                          {str(row.plan_id || row.invoice_number, "Invoice")}
                        </Link>
                      </td>
                      <td className="py-2 pr-3 font-mono tabular">
                        {row.amount_usd != null ? formatUsd(Number(row.amount_usd)) : "—"}
                      </td>
                      <td className="py-2">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${
                            paid
                              ? "bg-[var(--success-soft)] text-[var(--success)]"
                              : payable
                                ? "bg-amber-500/15 text-amber-400"
                                : "bg-[var(--surface-2)] text-[var(--fg-muted)]"
                          }`}
                        >
                          {status.replaceAll("_", " ")}
                        </span>
                      </td>
                      <td className="py-2 text-right">
                        {payable ? (
                          <a
                            href={rowPay || detailHref}
                            className="inline-flex h-8 items-center rounded-full bg-[var(--accent)] px-3 text-xs font-semibold text-[var(--accent-fg)]"
                          >
                            Pay now
                          </a>
                        ) : (
                          <Link href={detailHref} className="text-xs font-semibold text-[var(--accent)]">
                            View
                          </Link>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </SubCard>
    </div>
  );
}

function SubCard({
  icon,
  title,
  description,
  action,
  children,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="flex h-full min-w-0 flex-col rounded-[22px] border border-[color-mix(in_srgb,var(--accent)_32%,var(--border))] bg-[var(--surface)] p-4 shadow-[0_16px_36px_rgba(2,12,28,0.28),inset_0_1px_0_rgba(255,255,255,0.07)] sm:p-5 lg:min-h-[22rem]">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
            {icon}
          </span>
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-[var(--fg)]">{title}</h2>
            <p className="mt-0.5 text-xs leading-relaxed text-[var(--fg-muted)]">{description}</p>
          </div>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </section>
  );
}

function DetailRow({
  label,
  value,
  live = false,
}: {
  label: string;
  value: string;
  live?: boolean;
}) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-3 border-b border-[var(--border)] py-3 last:border-b-0">
      <p className="text-sm text-[var(--fg-muted)]">{label}</p>
      <p className={`shrink-0 text-sm font-semibold capitalize ${live ? "text-[var(--success)]" : "text-[var(--fg)]"}`}>
        {value}
      </p>
    </div>
  );
}
