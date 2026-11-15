# PHASE — Auth OTP, MFA & Onboarding Acceptance

**Date:** 2026-11-15  
**Merges:** `#281` (feature), `#284` (SHA docs), `#286` (MFA status bind), `#288` (recovery service role)  
**Supabase project:** `otqyhlmwaifokrczryrc`

## Summary

QuantForg registration verifies email with a six-digit OTP, lands users on Overview (`/dashboard`) after confirmation, and exposes optional TOTP MFA under Settings → Security. Google OAuth and existing sessions remain intact.

Production backend tip at acceptance close: **`a47ac527`** (`www.quantforg.com/qf-api/health`). Frontend remains the Ready preview from `#281` aliased to `www` (formal Vercel Production promote still blocked — see matrix).

## External acceptance matrix (2026-11-15)

| # | Check | Result | Evidence (secrets redacted) |
|---|--------|--------|-----------------------------|
| 1 | Real six-digit OTP email in test mailbox | **PASS** | Disposable Gmail via Emailnator. Subject `Your QuantForg verification code`; sender Resend `no-reply@auth.quantforg.com` / QuantForg; branded HTML OTP block. Digits not recorded. |
| 2 | Authenticator-app TOTP enrollment | **PASS** | Production enroll returned factor + RFC6238 secret; codes via standards-compliant TOTP (pyotp ≡ authenticator-app algorithm). |
| 3 | QR setup + manual secret setup | **PASS** | Enroll payload: non-empty `qr_code`, `secret` (≥16 chars), `otpauth://` `uri`. |
| 4 | Valid six-digit TOTP challenge | **PASS** | `POST /auth/mfa/verify` → **200**, `aal=aal2` (after `#286`/`#288`). |
| 5 | Invalid TOTP challenge | **PASS** | Rejected → **401** `invalid_mfa_code`. |
| 6 | Recovery code single-use | **PASS** | 8 codes issued; first consume **200**; reuse → **401** `invalid_recovery_code`. |
| 7 | MFA disable requires elevated auth | **PASS** | Unenroll at AAL1 → **401**; after TOTP to AAL2 → **200** disabled. |
| 8 | Google OAuth operational | **PASS** | `GET /auth/oauth/google` → **200** authorize URL; `/auth/callback` **200**. |
| 9 | Email OTP confirmation → `/dashboard` | **PASS** | Post-verify redirect to `/dashboard`; route **200** on www. |
| 10 | MFA-enabled users challenged at login | **PASS** | Login → `mfa_required=true`, `aal=aal1`; TOTP → `aal=aal2`. |
| 11 | Non-MFA users sign in normally | **PASS** | Without verified factor → `mfa_required=false`. |
| 12 | RLS: recovery hashes / MFA secrets not exposed | **PASS** | Anon REST on `auth_mfa_recovery_codes` → **401**. Service role OK; hashes only (no plaintext). |
| 13 | Vercel Production promotion workflow | **BLOCKED** | Promote rate-limit earlier; this session also local disk **ENOSPC** for Vercel CLI. www still via Ready-preview alias of `#281` frontend. |
| 14 | Production SHA + www routes | **PASS** | Health `commit_short=a47ac5273c99`. Routes **200**: `/verify-email`, `/mfa`, `/auth/callback`, `/dashboard`. |

**Overall:** Items **1–12** and **14** are **PASS**. Item **13** remains **BLOCKED** until Vercel promote is possible. Acceptance is not claimed fully complete while promote is blocked.

## Onboarding redirect behavior

| Flow | Result |
|------|--------|
| Register → verification pending | `/verify-email?email=…` (OTP entry) |
| OTP verify success | Session → `/dashboard` |
| Register with immediate session | `/dashboard` (not `/get-started`) |
| Email confirm hash / callback signup | `/dashboard` |
| Google OAuth callback | `/dashboard` |
| Product tour / first-run checklist | Not forced after login |

## Supabase OTP configuration

| Setting | Value |
|---------|-------|
| Project | `otqyhlmwaifokrczryrc` |
| OTP length | 6 |
| OTP expiry | 3600s |
| Confirmation subject | `Your QuantForg verification code` |
| Template | `{{ .Token }}` |
| MFA TOTP | Enabled |
| Migration | `20261115033000_auth_mfa_recovery_codes` applied |
| SMTP | Resend `no-reply@auth.quantforg.com` |

## Production fixes during acceptance

| PR | Issue | Fix |
|----|-------|-----|
| [#286](https://github.com/QuantForg1/QuantForg/pull/286) | `GET /auth/mfa/status` 401 | JWT-direct factor list/AAL; safe session bind |
| [#288](https://github.com/QuantForg1/QuantForg/pull/288) | Valid TOTP + recovery → 500 | Recovery store uses service-role `admin_client` |

## Recovery security

- Table stores HMAC-SHA256 hashes only; plaintext never persisted
- RLS deny for `anon`/`authenticated`; `service_role` only
- Single-use via `used_at` — verified in Production E2E

## Production deployment SHAs

| Service | SHA / deployment | Notes |
|---------|------------------|-------|
| Backend (Railway) | `a47ac527` | Includes #286 + #288 |
| Frontend (Vercel) | `#281` Ready preview aliased to www | Formal Production promote **BLOCKED** |
| Auth feature baseline | `#281` → `1951ce7b` | OTP/MFA feature merge |

## Owner checklist

- [x] No forced `/get-started` after signup/verify
- [x] Six-digit OTP path + mailbox evidence (redacted)
- [x] MFA enroll / valid / invalid / recovery single-use / disable
- [x] MFA login gate + non-MFA login
- [x] Google OAuth preserved
- [x] RLS recovery hashes not exposed to anon
- [x] Railway SHA `a47ac527` recorded
- [ ] Formal Vercel **Production** promote (BLOCKED — alias in place)
