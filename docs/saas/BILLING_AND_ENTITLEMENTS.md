# Billing & entitlements (crypto invoice, no free trial)

Updated 19 November 2026 so this note matches the code. It does not change prices, invoices, or entitlements.

## What the code does

- Plans: Starter ($49), Professional ($99), Premium ($199), from `app/domain/billing/plans.py` and `frontend/src/lib/billing/plans.ts`.
- A free trial is not offered. `BillingService.list_plans` returns `trial: None` and `trial_days: 0`. `start_trial` raises `TRIAL_DISCONTINUED` before any trial row is written. `FREE_TRIAL_AVAILABLE` is `false`.
- Creating an account, connecting MT5, and viewing balance do not require a subscription. Starting the robot does.
- Customer-facing payment method label: **Crypto Payment**. The processor name stays off normal customer UI. The privacy policy is the disclosure that names the processor.
- Checkout at `/billing/checkout`. Return at `/billing/return`. Invoices at `/billing/invoices`.
- Paid access is granted only after a verified finished payment. A browser return URL does not grant it.
- Automatic monthly crypto charging is not enabled. Renewal is a new invoice.
- `BILLING_GRACE_DAYS` and `BILLING_TRIAL_DAYS` remain server settings. The trial setting is not used to start a trial, because `start_trial` returns before it reads that value.

## Safe rules

1. Never grant paid access from a client-side button or return URL.
2. Never display the payment processor brand in normal customer UI.
3. Do not describe a free trial on marketing pages.
4. Do not enable automatic monthly charging from a documentation edit.

## Railway secrets

| Variable | Purpose |
|----------|---------|
| `NOWPAYMENTS_API_KEY` | LIVE API key (server-only) |
| `NOWPAYMENTS_IPN_SECRET` | LIVE IPN HMAC secret |
| `NOWPAYMENTS_API_BASE` | `https://api.nowpayments.io/v1` |
| `PUBLIC_APP_URL` | `https://www.quantforg.com` |
| `PUBLIC_API_URL` | Public API base including `/api/v1` |
| `BILLING_TRIAL_DAYS` | Unused for new trials while `start_trial` is discontinued |
| `BILLING_GRACE_DAYS` | Server grace setting. This note does not change it |

IPN callback: `{PUBLIC_API_URL}/billing/ipn/nowpayments`
