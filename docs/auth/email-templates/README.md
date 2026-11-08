# QuantForg email templates

Reference copies for **Supabase Auth** (dashboard-hosted) and **product billing** mail (future transactional provider). Apply HTML in Supabase **Authentication → Email Templates** for auth messages; product templates are for a future ESP when subscription notifications are wired.

## Auth templates (Supabase)

Paste from `confirm-signup`, `welcome`, `reset-password`, and `change-email`. Preserve Go template variables such as `{{ .ConfirmationURL }}` and `{{ .Token }}` exactly — they are required for links to work.

## Product templates (billing lifecycle)

`trial-activated`, `trial-expiring`, `trial-expired`, `payment-received`, `subscription-activated`, `invoice-created`, `payment-failed`, `subscription-renewal-reminder`, `subscription-expired`, `subscription-cancelled` describe SaaS state changes. Do not send these until a product email pipeline exists; until then, customers see status in **Settings → Subscription** and **Billing → Invoices**.

## Brand (RC4)

- Background charcoal `#111827` / surface `#151B23`
- Accent cyan `#00D4E0`
- Logo: https://www.quantforg.com/brand/quantforg-mark-256.png

Never promise trading profits. Use **Crypto Payment** in customer copy (not processor brand names).
