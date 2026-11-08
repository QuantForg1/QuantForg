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

export type PlanComparisonRow = {
  feature: string;
  trial: string;
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

export const TRIAL_DAYS = 7;

export const TRIAL_POSITIONING = `${TRIAL_DAYS}-day Starter access without payment details. One claim per customer. Does not auto-convert to a paid plan.`;

export const TRIAL_EXPIRES_BEHAVIOR =
  "When the trial ends, trial-only entitlements are revoked. Your account, profile, invoices, and history are preserved. Choose a paid plan to continue — you will not be charged automatically.";

export const TRIAL_FEATURES: readonly string[] = [
  "Access to QuantForg dashboard",
  "Live market research and chart access",
  "Strategy and signal exploration",
  "Controlled introduction to automated trading",
  "Auto-trading only through explicitly enabled, approved broker and risk configurations",
  "Basic portfolio and position visibility",
  "Essential risk visibility",
  "Limited research and support",
];

export const PLAN_COMPARISON_ROWS: readonly PlanComparisonRow[] = [
  {
    feature: "Dashboard & workspace",
    trial: "Included",
    starter: "Essential",
    professional: "Full",
    premium: "Full",
  },
  {
    feature: "Market research & charts",
    trial: "Included",
    starter: "Core",
    professional: "Expanded",
    premium: "Advanced",
  },
  {
    feature: "Strategy & signal exploration",
    trial: "Exploration",
    starter: "Standard",
    professional: "Expanded",
    premium: "Advanced",
  },
  {
    feature: "Broker connection workflows",
    trial: "Guided intro",
    starter: "Included",
    professional: "Included",
    premium: "Included",
  },
  {
    feature: "Automated trading access",
    trial: "Controlled intro",
    starter: "Core (risk-gated)",
    professional: "Enhanced (risk-gated)",
    premium: "Full eligible (risk-gated)",
  },
  {
    feature: "Portfolio & positions",
    trial: "Basic",
    starter: "Standard",
    professional: "Full workspace",
    premium: "Advanced",
  },
  {
    feature: "Risk controls",
    trial: "Essential visibility",
    starter: "Standard (enforced)",
    professional: "Standard (enforced)",
    premium: "Standard (enforced)",
  },
  {
    feature: "Analytics & monitoring",
    trial: "Limited",
    starter: "Core",
    professional: "Advanced",
    premium: "Enhanced",
  },
  {
    feature: "Support",
    trial: "Limited",
    starter: "Email",
    professional: "Priority",
    premium: "Priority + onboarding",
  },
  {
    feature: "License management",
    trial: "Trial license",
    starter: "Standard",
    professional: "Standard",
    premium: "Advanced",
  },
];

export const BILLING_PLANS: BillingPlan[] = [
  {
    id: "starter",
    licenseTier: "starter",
    name: "Starter",
    monthlyPriceUsd: 49,
    positioning: "Essential QuantForg workspace for individual operators.",
    ctaLabel: "Choose Starter",
    entitlements: [
      "Essential QuantForg workspace",
      "Core market research and chart access",
      "Standard strategy access",
      "Broker connection workflows",
      "Core automated trading capabilities (subject to eligibility and risk checks)",
      "Standard portfolio and position visibility",
      "Standard risk controls (never bypassed by plan)",
      "Email support",
    ],
  },
  {
    id: "professional",
    licenseTier: "professional",
    name: "Professional",
    monthlyPriceUsd: 99,
    positioning: "Expanded tools for active professional desks.",
    highlighted: true,
    ctaLabel: "Choose Professional",
    entitlements: [
      "Everything in Starter",
      "Expanded strategy and research tools",
      "Advanced analytics surfaces",
      "Portfolio and performance workspaces",
      "Enhanced trading insights and monitoring",
      "Priority product support",
      "Professional operator features",
    ],
  },
  {
    id: "premium",
    licenseTier: "enterprise",
    name: "Premium",
    monthlyPriceUsd: 199,
    positioning: "Full eligible platform access with enhanced support.",
    ctaLabel: "Choose Premium",
    entitlements: [
      "Everything in Professional",
      "Full eligible platform feature access",
      "Advanced research and strategy tools",
      "Enhanced analytics and reporting",
      "Advanced monitoring and account management",
      "Priority support",
      "Premium onboarding assistance",
      "Advanced license management",
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
