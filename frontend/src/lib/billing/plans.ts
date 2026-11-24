/**
 * QuantForg SaaS plan catalog (marketing + entitlement keys).
 *
 * Server-side Crypto Payment (LIVE) creates invoices; paid access is granted
 * only after verified IPN (`payment_status=finished`). Client clicks never activate access.
 *
 * DB license tiers: starter / professional / enterprise (Premium → enterprise).
 * No free trial or free plan: the robot runs only on an active paid license.
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

export type PlanComparisonRow = {
  feature: string;
  unpaid: string;
  starter: string;
  professional: string;
  premium: string;
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

/** Free trial and free plan are discontinued: the robot runs on a paid plan. */
export const FREE_TRIAL_AVAILABLE = false;

/** What an account without a subscription can and cannot do. */
export const UNPAID_ACCESS: readonly { feature: string; allowed: boolean }[] = [
  { feature: "Create an account and sign in", allowed: true },
  { feature: "Connect your MT5 broker", allowed: true },
  { feature: "Broker verification", allowed: true },
  { feature: "View balance, equity and margin", allowed: true },
  { feature: "View strategies and market research", allowed: true },
  { feature: "QuantForg AI assistant & chart screenshot analysis", allowed: true },
  { feature: "Trading signals", allowed: false },
  { feature: "Start the robot", allowed: false },
  { feature: "Open new trades / automated execution", allowed: false },
];

export const PLAN_COMPARISON_ROWS: readonly PlanComparisonRow[] = [
  {
    feature: "Account, broker connection & verification",
    unpaid: "Included",
    starter: "Included",
    professional: "Included",
    premium: "Included",
  },
  {
    feature: "Balance, equity & broker details",
    unpaid: "Included",
    starter: "Included",
    professional: "Included",
    premium: "Included",
  },
  {
    feature: "Start the robot / automated trading",
    unpaid: "Subscription required",
    starter: "Included",
    professional: "Included",
    premium: "Included",
  },
  {
    feature: "Verified broker accounts",
    unpaid: "1 (view only)",
    starter: "1",
    professional: "1",
    premium: "1",
  },
  {
    feature: "QuantForg AI assistant & chart screenshot analysis",
    unpaid: "Included",
    starter: "Included",
    professional: "Included",
    premium: "Included",
  },
  {
    feature: "Strategies & signals",
    unpaid: "Strategies only (signals locked)",
    starter: "Core",
    professional: "Expanded",
    premium: "Full eligible",
  },
  {
    feature: "Analytics & reports",
    unpaid: "Basic",
    starter: "Essential",
    professional: "Advanced",
    premium: "Advanced + reporting",
  },
  {
    feature: "Risk controls",
    unpaid: "Your risk profile",
    starter: "Enforced",
    professional: "Enforced",
    premium: "Enforced",
  },
  {
    feature: "Support",
    unpaid: "Help center",
    starter: "Email",
    professional: "Priority",
    premium: "Priority + onboarding",
  },
];

export const BILLING_PLANS: BillingPlan[] = [
  {
    id: "starter",
    licenseTier: "starter",
    name: "Starter",
    monthlyPriceUsd: 199,
    positioning: "For individual traders starting with automated trading.",
    ctaLabel: "Choose Starter",
    entitlements: [
      "QuantForg dashboard",
      "Live market data and chart access",
      "Core strategies and signals",
      "1 verified broker account",
      "1 active robot",
      "Essential analytics and portfolio visibility",
      "Standard risk management (your own risk profile)",
      "Standard email support",
      "Subscription-controlled LIVE execution",
    ],
  },
  {
    id: "professional",
    licenseTier: "professional",
    name: "Professional",
    monthlyPriceUsd: 399,
    positioning: "For active traders who need expanded trading intelligence.",
    highlighted: true,
    ctaLabel: "Choose Professional",
    entitlements: [
      "Everything in Starter",
      "Expanded strategy access",
      "Advanced analytics and performance reports",
      "Enhanced market and risk monitoring",
      "Advanced portfolio workspace",
      "Priority support",
    ],
  },
  {
    id: "premium",
    licenseTier: "enterprise",
    name: "Premium",
    monthlyPriceUsd: 799,
    positioning: "For advanced operators who want every eligible tool.",
    ctaLabel: "Choose Premium",
    entitlements: [
      "Everything in Professional",
      "Full eligible strategy access",
      "Advanced analytics and reporting",
      "Enhanced account and execution monitoring",
      "Advanced license management",
      "Premium onboarding",
      "Priority support",
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

/** ISO timestamps from billing API — UTC calendar dates for customer-facing UI. */
export function formatBillingDate(iso: string | null | undefined): string {
  if (!iso || !iso.trim()) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(parsed);
}

/** Annual billing is not offered until a recurring provider supports it. */
export const ANNUAL_BILLING_SUPPORTED = false;
