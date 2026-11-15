# PHASE — Auth OTP, MFA & Onboarding Acceptance

**Date:** 2026-11-15  
**Branch:** `feature/auth-otp-mfa-onboarding`  
**Supabase project:** `otqyhlmwaifokrczryrc` (verified via CLI linked project-ref)

## Summary

QuantForg registration now verifies email with a six-digit OTP, lands users on Overview (`/dashboard`) after confirmation, and exposes optional TOTP MFA under Settings → Security. Google OAuth and existing sessions remain intact.

## Onboarding redirect behavior

| Flow | Result |
|------|--------|
| Register → verification pending | `/verify-email?email=…` (OTP entry) |
| OTP verify success | Session established → `/dashboard` |
| Register with immediate session | `/dashboard` (not `/get-started`) |
| Email confirm hash / callback signup | `/dashboard` |
| Google OAuth callback | `/dashboard` (unchanged) |
| Product tour | Auto-dismissed; does not open after login |
| First-run checklist | No longer auto-presented; optional via Settings / Support |
| Get-started guide | Optional link in Settings → Preferences and Support |

Overview is never blocked by incomplete onboarding steps.

## Supabase OTP configuration

Verified project ref: `otqyhlmwaifokrczryrc`.

| Setting | Value |
|---------|-------|
| Email confirmations | Enabled |
| OTP length | 6 |
| OTP expiry | 3600s (1 hour) |
| Resend throttle | `max_frequency = 1m` |
| MFA TOTP enroll/verify | Enabled |
| Confirmation subject | `Your QuantForg verification code` |
| Template variable | `{{ .Token }}` (numeric OTP; not ConfirmationURL-primary) |
| Migration | `20261115033000_auth_mfa_recovery_codes` applied on remote |

`supabase config push` / `db push` report Production up to date for declared Auth + migration properties. SMTP sender remains Resend `no-reply@auth.quantforg.com` / QuantForg (unchanged remote SMTP secrets).

## Email template verification

Local template: `supabase/templates/confirmation.html`

- Brand header + institutional charcoal/cyan styling  
- Large `{{ .Token }}` OTP block  
- Expiry + security notices  
- Support link: `https://www.quantforg.com/support`  
- CTA opens `/verify-email` (no magic-link as primary mechanism)

## OTP signup & verification (application)

Backend:

- `POST /auth/verify-email` accepts `{ email, token }` (6 digits) or legacy `{ token_hash }`
- `POST /auth/resend-verification` (anti-enumeration message)
- Adapter uses Supabase `verify_otp` with `type: "email"` (per current Supabase docs; `signup`/`magiclink` deprecated)

Frontend:

- Premium six-box OTP UI with paste, backspace, focus advance, mobile numeric keyboard
- Resend cooldown (60s)
- Invalid / expired / rate-limit messaging
- No OTP values in URLs, logs, or analytics payloads

Unit tests: `tests/unit/test_use_cases_auth.py` — **12 passed** (OTP + legacy hash paths).

## MFA enrollment & challenge

| Capability | Endpoint / UI |
|------------|---------------|
| Status / AAL | `GET /auth/mfa/status` |
| Enroll TOTP | `POST /auth/mfa/enroll` → Settings → Security panel |
| Challenge | `POST /auth/mfa/challenge` |
| Verify | `POST /auth/mfa/verify` (+ optional recovery issue) |
| Unenroll | `POST /auth/mfa/unenroll` |
| Recovery generate | `POST /auth/mfa/recovery/generate` |
| Recovery consume | `POST /auth/mfa/recovery/consume` |
| Login challenge UI | `/mfa` when `mfa_required` |
| App shell gate | `qf_mfa_pending` redirects to `/mfa` until verified |

MFA is optional by default; existing users are not force-enrolled.

## Recovery security

- Table `public.auth_mfa_recovery_codes` stores **HMAC-SHA256 hashes only**
- RLS restrictive deny for `anon`/`authenticated`; grants to `service_role`
- Codes shown once at generation; reuse prevented via `used_at`
- Plaintext codes never persisted

## Google OAuth regression

- Callback path `/auth/callback` preserved
- OAuth users are not forced through email OTP when the provider confirms email
- MFA still applies when a verified TOTP factor exists

## Desktop / mobile / a11y

| Surface | Notes |
|---------|-------|
| Verify email | Responsive OTP boxes; `inputMode=numeric`; keyboard nav; `role=alert` errors |
| MFA challenge | Authenticator + recovery modes |
| Settings MFA | QR (SVG/data URL) + manual secret; recovery list once |
| Auth shell | Existing institutional AuthShell language |

Automated UI screenshots deferred to post-deploy browser pass on the PR preview / Production alias.

## Database / RLS / security findings

- Recovery table RLS deny-all for public roles: **PASS**
- No user-editable metadata used as MFA proof: factors + AAL from Supabase MFA APIs
- Sensitive secrets (OTP, TOTP secret, recovery plaintext) excluded from audit metadata
- No changes to billing, entitlements, trading core, or `ite_ops_alerts`

## Quality gates (pre-PR)

| Gate | Result |
|------|--------|
| `tsc --noEmit` (frontend) | PASS |
| ESLint (changed auth UI files) | PASS |
| Auth unit tests (`--no-cov`) | 12 passed |
| Supabase project ref | `otqyhlmwaifokrczryrc` |
| Migration remote | Applied |

## Production deployment SHAs

_Filled after Railway/Vercel promotion of this PR._

| Service | SHA / deployment | Notes |
|---------|------------------|-------|
| Backend (Railway) | _pending PR merge_ | |
| Frontend (Vercel) | _pending PR merge_ | Do not claim Production if promote is rate-limited; use Ready alias if required |
| Supabase Auth | Config already matches declared OTP/MFA template settings | |

## Remaining external blockers

1. Live mailbox proof of six-digit delivery requires a disposable registration against Production SMTP (Resend) — run on deployed SHA.
2. Authenticator-app E2E (QR scan + TOTP) requires a real enrolled factor on a test account after deploy.
3. Vercel Production promote may hit deploy quota; fallback is Ready-preview alias (same pattern as PR #278).

## Owner acceptance checklist

- [x] No forced `/get-started` after signup/verify  
- [x] Six-digit OTP verification path implemented (`type: email`)  
- [x] Premium confirmation email template with `{{ .Token }}`  
- [x] Premium verify-email page  
- [x] Optional MFA TOTP + recovery hashes  
- [x] Google OAuth path preserved  
- [ ] Live Production email delivery evidence (post-deploy)  
- [ ] Deployed Railway + Vercel SHAs recorded  
