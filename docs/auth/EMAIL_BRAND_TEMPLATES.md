# Auth email brand guidance (Supabase Dashboard)

QuantForg does not store HTML transactional email templates in this repository. Password reset and confirmations are sent by **Supabase Auth**.

Apply brand consistency in the Supabase project:

1. Authentication → Email Templates
2. Use charcoal background `#111827`, cyan accent `#00D4E0`, white/silver text
3. Logo URL (public): `https://www.quantforg.com/brand/quantforg-mark-256.png`
4. Preserve existing `{{ .ConfirmationURL }}` / `{{ .Token }}` variables — do not break reset links
5. Subjects should say “QuantForg” without promising trading profits

Suggested confirm button style: solid cyan (`#00D4E0`) on charcoal, IBM Plex / system sans, mobile-friendly single column ≤ 600px.
