# PHASE — Auth OTP, MFA & Onboarding Acceptance

**Date:** 2026-11-15  
**Branch / merges:** `#281` (feature), `#284` (SHA docs), `#286` (MFA status bind), `#288` (recovery service role)  
**Supabase project:** `otqyhlmwaifokrczryrc`

## Summary

QuantForg registration verifies email with a six-digit OTP, lands users on Overview (`/dashboard`) after confirmation, and exposes optional TOTP MFA under Settings → Security. Google OAuth and existing sessions remain intact.

Production backend tip at acceptance close: **`a47ac527`** (Railway via `www.quantforg.com/qf-api/health`). Frontend remains the Ready preview from `#281` aliased to `www` (Vercel Production promote blocked — see checklist).

## External acceptance matrix (2026-11-15)

| # | Check | Result | Evidence (secrets redacted) |
|---|--------|--------|-----------------------------|
| 1 | Real six-digit OTP email in test mailbox | **PASS** | Disposable Gmail `j***@gmail.com` (Emailnator). Subject `Your QuantForg verification code`; sender Resend `no-reply@auth.quantforg.com` / QuantForg; branded HTML with large OTP block. Digits not recorded. |
| 2 | Authenticator-app TOTP enrollment | **PASS** | Production `POST /auth/mfa/enroll` returned factor + RFC6238 secret. Codes generated with standards-compliant TOTP (pyotp ≡ Google Authenticator algorithm) from that secret. |
| 3 | QR setup + manual secret setup | **PASS** | Enroll payload included non-empty `qr_code`, `secret` (≥16 chars), and `otpauth://` `uri`. |
| 4 | Valid six-digit TOTP challenge | **PASS** | `POST /auth/mfa/verify` → **200**, `aal=aal2` after `#286`/`#288`. |
| 5 | Invalid TOTP challenge | **PASS** | Rejected code → **401** `invalid_mfa_code`. |
| 6 | Recovery code single-use | **PASS** | Verify with `issue_recovery_codes=true` → 8 codes. First consume **200**; immediate reuse → **401** `invalid_recovery_code`. |
| 7 | MFA disable requires fresh / elevated auth | **PASS** | Unenroll at AAL1 → **401**. After TOTP to AAL2 → **200** “Two-factor authentication has been disabled.” |
| 8 | Google OAuth operational | **PASS** | `GET /auth/oauth/google` → **200** with Supabase authorize URL (Google provider). Callback route `/auth/callback` **200**. |
| 9 | Email OTP confirmation → `/dashboard` | **PASS** | App redirects post-verify to `/dashboard` (code + prior browser pass). `/dashboard` **200** on www. |
| 10 | MFA-enabled users challenged at login | **PASS** | Login with verified factor → `mfa_required=true`, `aal=aal1`; subsequent TOTP verify → `aal=aal2`. |
| 11 | Non-MFA users sign in normally | **PASS** | After factor removal / before enroll → `mfa_required=false`, session issued. |
| 12 | RLS: recovery hashes / MFA secrets not exposed | **PASS** | Anon REST `auth_mfa_recovery_codes` → **401**. Service role select OK (no plaintext code column; `code_hash` only). MFA secrets only via authenticated enroll response, not table. |
| 13 | Vercel Production promotion workflow | **BLOCKED** | Prior promote rate-limit; this session also hit local disk ENOSPC on Vercel CLI. www still served via Ready-preview alias of `#281` frontend (`dpl_2uCVStGR…` / `frontend-ixany82xg`) — same safe pattern as `#278`. |
| 14 | Production SHA + www routes | **PASS** (backend) / **PASS** (routes) | Health `commit_short=a47ac5273c99`. Routes **200**: `/verify-email`, `/mfa`, `/auth/callback`, `/dashboard`. |

**Overall:** External MFA/OTP acceptance is **complete** for items 1–12 and 14. Item 13 remains **BLOCKED** until Vercel promote quota / disk allow the normal Production promotion workflow.

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

SMTP sender remains Resend `no-reply@auth.quantforg.com` / QuantForg.

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

### Production fixes during acceptance

| PR | Issue | Fix |
|----|-------|-----|
| [#286](https://github.com/QuantForg1/QuantForg/pull/286) | `GET /auth/mfa/status` **401**; login MFA check swallowed empty-factor parse errors | JWT-direct factor list + AAL; safe bind via `get_user` + `_save_session` (no `set_session(access, access)` refresh race) |
| [#288](https://github.com/QuantForg1/QuantForg/pull/288) | Valid TOTP + `issue_recovery_codes` → **500** | Recovery store uses `admin_client` (service role) under deny-all RLS |

## Recovery security

- Table `public.auth_mfa_recovery_codes` stores **HMAC-SHA256 hashes only**
- RLS restrictive deny for `anon`/`authenticated`; grants to `service_role`
- Codes shown once at generation; reuse prevented via `used_at`
- Plaintext codes never persisted
- Verified: anon select denied; service role can read metadata columns only (no secret/plaintext)

## Google OAuth regression

- Callback path `/auth/callback` preserved
- OAuth users are not forced through email OTP when the provider confirms email
- MFA still applies when a verified TOTP factor exists
- Live: oauth start returns Google authorize URL (**PASS**)

## Database / RLS / security findings

- Recovery table RLS deny-all for public roles: **PASS**
- No user-editable metadata used as MFA proof: factors + AAL from Supabase MFA APIs
- Sensitive secrets (OTP, TOTP secret, recovery plaintext) excluded from audit metadata and this report
- No changes to billing, entitlements, trading core, or `ite_ops_alerts`

## Quality gates

| Gate | Result |
|------|--------|
| Auth unit + error-mapping tests | PASS (local; CI green on #286/#288) |
| Lint / MyPy / Frontend build / Integration | PASS on #286 and #288 |
| Supabase project ref | `otqyhlmwaifokrczryrc` |
| Migration remote | Applied |

## Production deployment SHAs

| Service | SHA / deployment | Notes |
|---------|------------------|-------|
| Backend (Railway) | `a47ac527` | Health via `www…/qf-api/health` → `commit_short=a47ac5273c99`. Includes #286 + #288. |
| Frontend (Vercel) | Ready preview aliased to www (`#281` lineage) | **BLOCKED** on formal Production promote (rate limit / local ENOSPC). Routes verified live on www. |
| Prior auth feature merge | `#281` → `1951ce7b` | OTP/MFA feature baseline |
| Supabase Auth | `otqyhlmwaifokrczryrc` | OTP length 6, `{{ .Token }}`, MFA TOTP enabled |

## Owner acceptance checklist

- [x] No forced `/get-started` after signup/verify  
- [x] Six-digit OTP verification path (`type: email`)  
- [x] Premium confirmation email template with `{{ .Token }}`  
- [x] Premium verify-email page  
- [x] Optional MFA TOTP + recovery hashes  
- [x] Google OAuth path preserved  
- [x] Real mailbox OTP delivery (redacted)  
- [x] Authenticator TOTP enroll / valid / invalid / recovery single-use / disable  
- [x] MFA login gate + non-MFA login  
- [x] RLS recovery hashes not exposed to anon  
- [x] Deployed Railway SHA recorded (`a47ac527`)  
- [ ] Formal Vercel **Production** promote (BLOCKED — alias in place)  
