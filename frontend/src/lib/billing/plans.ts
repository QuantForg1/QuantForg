/**
 * QuantForg SaaS plan catalog (marketing + entitlement keys).
 *
 * Server-side Crypto Payment (LIVE) creates invoices; paid access is granted
 * only after verified IPN (`payment_status=finished`). Client clicks never activate access.
 *
 * DB license tiers: starter / professional / enterprise (Premium → enterprise).
 * Free trial uses license tier `trial` with Starter entitlements for 7 days.
 */

export type PlanId = "starter" | "professional" | "premium";

export type BillingPlan = {
  id: PlanId;
  /** Existing license.tier value used by backend / DB. */
  licenseTier: "starter" | "professional" | "enterprise";
  name: string;
  monthlyPriceUsd: number;
  positioning: string;
  highlighted?: boolean;
  entitlements: string[];
  ctaLabel: string;
};

/** Customer-facing payment method — never display processor brand in UI. */
export const PAYMENT_METHOD_LABEL = "Crypto Payment";

/** Honest defaults for customer UI until `/billing/provider` responds. */
export const BILLING_PROVIDER = {
  configured: true,
  paymentMethod: "crypto" as const,
  paymentMethodLabel: PAYMENT_METHOD_LABEL,
  mode: "live" as const,
  recurringSupported: false,
  note:
    "Pay with Crypto Payment. Paid access activates only after QuantForg verifies a completed payment — never from a browser redirect alone. Automatic monthly crypto charging is not enabled; renew with a new invoice.",
} as const;

export const TRIAL_DAYS = 7;

export const BILLING_PLANS: BillingPlan[] = [
  {
    id: "starter",
    licenseTier: "starter",
    name: "Starter",
    monthlyPriceUsd: 49,
    positioning: "Essential QuantForg platform access for individual operators.",
    ctaLabel: "Choose Starter",
    entitlements: [
      "Authenticated workspace access",
      "MT5 broker connection workflows",
      "Core market research surfaces",
      "Standard risk controls enforced by the platform",
      "Email support",
    ],
  },
  {
    id: "professional",
    licenseTier: "professional",
    name: "Professional",
    monthlyPriceUsd: 99,
    positioning: "Advanced platform functionality for active desks.",
    highlighted: true,
    ctaLabel: "Choose Professional",
    entitlements: [
      "Everything in Starter",
      "Expanded strategy and research tooling",
      "Portfolio and performance workspaces",
      "Priority product support",
      "Seat for a professional operator",
    ],
  },
  {
    id: "premium",
    licenseTier: "enterprise",
    name: "Premium",
    monthlyPriceUsd: 199,
    positioning: "Higher-tier platform access and enhanced support.",
    ctaLabel: "Choose Premium",
    entitlements: [
      "Everything in Professional",
      "Enhanced onboarding assistance",
      "Priority support response",
      "License center coordination for operators",
      "Best-effort account isolation guidance",
    ],
  },
];

export function getPlan(id: string | null | undefined): BillingPlan | undefined {
  if (!id) return undefined;
  return BILLING_PLANS.find((plan) => plan.id === id);
}

export function formatUsd(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
}

/** Annual billing is not offered until a recurring provider supports it. */
export const ANNUAL_BILLING_SUPPORTED = false;
