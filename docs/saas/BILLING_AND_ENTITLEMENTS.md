# Billing & entitlements (NOWPayments LIVE)

## What exists

- Marketing plans: Starter ($49), Professional ($99), Premium ($199) in `frontend/src/lib/billing/plans.ts` and `app/domain/billing/plans.py`
- Pricing UI + checkout at `/pricing` and `/billing/checkout`
- Settings → Subscription reads `/billing/me`
- LIVE NOWPayments invoice creation: `POST /api/v1/billing/checkout`
- LIVE IPN webhook: `POST /api/v1/billing/ipn/nowpayments` (HMAC `x-nowpayments-sig`)
- Tables: `billing_orders`, `billing_webhook_events`, `contact_leads`
- License activation on verified `payment_status=finished` only
- Manual renewal model (new invoice) — automatic recurring crypto is **not** claimed

## Safe rules

1. Never grant paid access from a client-side button or return URL.
2. Entitlement changes only after verified IPN + signature + amount/order checks.
3. Do not invent payment credentials or use the sandbox host.
4. Contact / register may record plan **intent** only until payment finishes.

## Railway secrets (required for LIVE checkout)

| Variable | Purpose |
|----------|---------|
| `NOWPAYMENTS_API_KEY` | LIVE API key |
| `NOWPAYMENTS_IPN_SECRET` | LIVE IPN HMAC secret |
| `NOWPAYMENTS_API_BASE` | Must remain `https://api.nowpayments.io/v1` |
| `PUBLIC_APP_URL` | `https://www.quantforg.com` |
| `PUBLIC_API_URL` | Public API base including `/api/v1` for IPN |

NOWPayments dashboard IPN / callback URL:

`https://<your-public-api>/api/v1/billing/ipn/nowpayments`

## Recurring billing

Automatic NOWPayments recurring subscriptions are **not** enabled in this deployment.
Customers renew by creating a new LIVE invoice. If the merchant later enables recurring
APIs, integrate only after confirming the official contract — do not invent endpoints.

## Migrations

- `supabase/migrations/20261108180000_saas_billing.sql`
- `supabase/migrations/20261108180100_saas_billing_rls.sql`
