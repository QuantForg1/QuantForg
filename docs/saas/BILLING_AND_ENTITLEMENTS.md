# Billing & entitlements (honest status)

## What exists

- Marketing plans: Starter ($49), Professional ($99), Premium ($199) in `frontend/src/lib/billing/plans.ts`
- Pricing UI + comparison table at `/pricing`
- Settings → Subscription panel (no fake paid state)
- Existing license domain + COP license center (manual activate / suspend / revoke)
- DB license tiers: `trial | starter | professional | enterprise`  
  Marketing **Premium** maps to `enterprise`

## What does not exist

- Stripe / Paddle / Lemon Squeezy (or any) recurring checkout
- Payment webhooks
- Customer billing portal / invoice ledger tables
- Annual billing (intentionally hidden until supported)

## Safe rules

1. Never grant paid access from a client-side button.
2. Entitlement changes only after verified payment + server-side license activation.
3. Do not invent payment credentials.
4. Contact / register flows may record plan **intent** only.

## Required to enable self-serve checkout later

1. Choose a provider and store secrets only on Railway (server).
2. Add webhook signature verification.
3. Map successful invoices → `licenses` row (tier + status + expires_at).
4. Flip `BILLING_PROVIDER.configured` only after end-to-end verified payments in production.
