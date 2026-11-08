# QuantForg email templates

Reference copies for **Supabase Auth** (Management API / dashboard) and **product billing** mail (`billing_email_notifications` + Resend).

## Auth templates (Supabase)

Apply with:

```bash
export SUPABASE_ACCESS_TOKEN="…"   # Dashboard → Account → Access Tokens
export SUPABASE_PROJECT_REF="otqyhlmwaifokrczryrc"
python scripts/apply_supabase_auth_email_templates.py
```

Sources: `confirm-signup`, `welcome`, `reset-password`, `change-email`. Preserve Go variables such as `{{ .ConfirmationURL }}` and `{{ .Token }}` exactly.

Production already enables email confirmations and Google OAuth (verified via `supabase config pull --dry-run`).

## Product templates (billing lifecycle)

Queued into `billing_email_notifications` by the billing service. Delivery uses **Resend** when `RESEND_API_KEY` is set on Railway (`BILLING_EMAIL_FROM` optional). Without the key, queued rows are marked `skipped` with `email_provider_not_configured` — never reported as delivered.

Keys: trial activated/expiring/expired, invoice created, payment pending/confirmed/failed/expired, subscription activated/upgraded/downgraded/past due/expired/cancelled, renewal reminder.

## Brand (RC4)

- Background charcoal `#111827` / surface `#151B23`
- Accent cyan `#00D4E0`
- Logo: https://www.quantforg.com/brand/quantforg-mark-256.png

Never promise trading profits. Use **Crypto Payment** in customer copy (not processor brand names).
