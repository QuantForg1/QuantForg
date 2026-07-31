# Owner Login Recovery Report

**Date:** 2026-07-31 (UTC)  
**Scope:** Diagnose and restore owner password login only  
**Account:** `p7provider@gmail.com`  
**Environment:** Production (`quantforg-production.up.railway.app` + Supabase project `otqyhlmwaifokrczryrc`)

---

## Root cause

The owner **account existed and was healthy** in Supabase Auth and in `public.users`:

| Check | Result |
|---|---|
| Auth user present | Yes (`auth.users`) |
| Email confirmed | Yes |
| Banned / deleted | No |
| Password hash present | Yes (bcrypt length 60) |
| Email identity present | Yes (`auth.identities` provider=`email`) |
| App profile | Yes — `role=owner`, `status=active` |
| Auth ↔ profile link | `public.users.auth_user_id` matched |

Production API login returned:

```json
{ "error": { "code": "invalid_credentials", "message": "Invalid login credentials" } }
```

That maps to Supabase GoTrue rejecting the password (`sign_in_with_password` / `invalid login credentials`).

**Conclusion:** The stored password hash did **not** match the owner’s expected password. Configuration, email verification, ban state, profile/RLS, and frontend session plumbing were not the failure point.

---

## Investigation summary

1. **Auth provider:** Supabase Auth (QuantForg project `otqyhlmwaifokrczryrc`) — confirmed via Railway `SUPABASE_URL`.
2. **Account state:** Active, confirmed, not banned; last sign-in existed (token/session path worked historically).
3. **Email confirmation:** Satisfied (`email_confirmed_at` set).
4. **Password hash:** Present but invalid for the provided credentials → Admin password reset required.
5. **App profile:** Owner role preserved (`public.users.role = owner`, `status = active`).
6. **Frontend flow:** Unchanged. Tokens stored in `localStorage` / `sessionStorage` per `frontend/src/lib/auth/session.ts` (Remember Me). No cookie BFF; not implicated.
7. **Post-login profile:** `/api/v1/auth/me` returns owner profile after successful login.
8. **Middleware / route guards:** Owner ops route `/api/v1/ite/ops/rc1-production-validation` returned **200** with bearer after fix.
9. **No duplicate owner account created.**

---

## Fix applied

Used Supabase Auth **Admin API** (`PUT /auth/v1/admin/users/{id}`) with the service role to:

- Reset the password securely
- Keep `email_confirm: true`
- Preserve `app_metadata.providers = ["email"]`
- Leave `public.users` role/status untouched

No application source code was modified for the fix.

---

## Files changed

| Path | Change |
|---|---|
| `docs/auth/OWNER_LOGIN_RECOVERY_REPORT.md` | This report only |

**Application / backend / frontend / auth architecture:** **unchanged**.

---

## Verification results

| Step | Result |
|---|---|
| Supabase password grant (`/auth/v1/token?grant_type=password`) | **OK** — access + refresh tokens issued |
| `POST /api/v1/auth/login` | **OK** — session issued |
| User payload | `role=owner`, `status=active`, email match |
| `GET /api/v1/auth/me` | **200** — owner profile |
| Owner ops dashboard probe (`/api/v1/ite/ops/rc1-production-validation`) | **200** |
| `POST /api/v1/auth/logout` | **200** |
| `GET /api/v1/auth/me` after logout | **401** (session invalidated as expected) |
| Re-login | **OK** — owner role still `owner` / `active` |
| DB profile after recovery | `role=owner`, `status=active`, `auth_user_id` unchanged |

Owner permissions are role-based (`role=owner`); no permission list regression observed.

---

## Credentials handling

- Password was used only in ephemeral local process env / Admin API calls.
- Password was **not** written into source, commits, or this report.
- Temporary secret files under `/tmp` were deleted after verification.
- No credentials hard-coded in the repository.

**Confirmation: no credentials were exposed in code or commits.**

---

## Residual notes

- Railway already stored matching E2E owner email for smoke tests; the Auth hash had drifted from that expected password — reset restored alignment.
- No deploy was required (Auth-side fix only).
- Recommend the owner rotate the password again via Settings → Change password after first successful login if operational policy requires unique non-shared credentials.
