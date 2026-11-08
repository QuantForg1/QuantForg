/**
 * QuantForg SaaS plan catalog (marketing + entitlement keys).
 *
 * Server-side NOWPayments LIVE checkout creates invoices; paid access is granted
 * only after verified IPN (`payment_status=finished`). Client clicks never activate access.
 *
 * DB license tiers: starter / professional / enterprise.
 * Marketing "Premium" maps to the existing `enterprise` license tier.
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

/** Recurring billing provider status for this deployment (honest defaults). */
export const BILLING_PROVIDER = {
  /** Flipped true when `/billing/provider` reports configured LIVE NOWPayments. */
  configured: true,
  provider: "nowpayments" as const,
  mode: "live" as const,
  recurringSupported: false,
  note:
    "Crypto checkout uses NOWPayments LIVE invoices. Paid access activates only after the backend verifies a finished payment notification — never from a browser redirect alone. Automatic recurring crypto billing is not enabled; renew with a new invoice.",
} as const;

export const BILLING_PLANS: BillingPlan[] = [
  {
    id: "starter",
    licenseTier: "starter",
    name: "Starter",
    monthlyPriceUsd: 49,
    positioning: "Entry-level access for customers exploring the platform.",
    ctaLabel: "Start with Starter",
    entitlements: [
      "Authenticated workspace access",
      "MT5 broker connection workflows",
      "Core market research surfaces",
      "Risk controls already enforced by the platform",
      "Email support",
    ],
  },
  {
    id: "professional",
    licenseTier: "professional",
    name: "Professional",
    monthlyPriceUsd: 99,
    positioning: "Advanced access for customers who need more platform functionality.",
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

/**
 * Annual billing is not offered until a recurring provider supports it.
 */
export const ANNUAL_BILLING_SUPPORTED = false;
