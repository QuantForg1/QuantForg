# Billing & entitlements (Crypto Payment + Starter trial)

## What exists

- Plans: Starter ($49), Professional ($99), Premium ($199)
- 7-day Starter free trial (one per verified customer) — no automatic charge
- Customer-facing payment method label: **Crypto Payment** (processor brand stays internal)
- Checkout at `/billing/checkout` (requires AuthProvider layout)
- Return at `/billing/return`
- Invoices at `/billing/invoices` and `/billing/invoices/[orderCode]`
- Settings → Subscription reflects server trial / paid / pending / expired state
- LIVE invoice creation + IPN verification; entitlements only on verified `finished`

## Safe rules

1. Never grant paid access from a client-side button or return URL.
2. Never display the payment processor brand in normal customer UI.
3. Trial does not auto-charge and cannot be claimed twice per identity.
4. Automatic monthly crypto charging is **not** enabled — renew with a new invoice.

## Railway secrets

| Variable | Purpose |
|----------|---------|
| `NOWPAYMENTS_API_KEY` | LIVE API key (server-only) |
| `NOWPAYMENTS_IPN_SECRET` | LIVE IPN HMAC secret |
| `NOWPAYMENTS_API_BASE` | `https://api.nowpayments.io/v1` |
| `PUBLIC_APP_URL` | `https://www.quantforg.com` |
| `PUBLIC_API_URL` | Public API base including `/api/v1` |
| `BILLING_TRIAL_DAYS` | Optional (default 7) |
| `BILLING_GRACE_DAYS` | Optional (default 3) |

IPN callback: `{PUBLIC_API_URL}/billing/ipn/nowpayments`
