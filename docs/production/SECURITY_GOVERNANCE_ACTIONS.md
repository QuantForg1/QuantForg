# Security and governance: owner actions (16 Nov 2026)

## Supabase: Leaked Password Protection (security advisor WARN)

Supabase checks new and changed passwords against HaveIBeenPwned and rejects known-leaked ones. Existing passwords and existing sessions are not affected.

1. Supabase dashboard → project `otqyhlmwaifokrczryrc` (Production) → **Authentication** → **Providers** → **Email**. On newer dashboards it is under **Authentication → Settings → Password security**.
2. Turn on **Prevent use of leaked passwords**. Optionally also set a minimum length of 10 or more and require letters + digits.
3. Save, then re-run the security advisor. The finding `auth_leaked_password_protection` should be gone.

This is a project setting with no SQL or API exposed to the agent, so the owner must turn it on in the dashboard.

## GitHub repository

| Item | Status (16 Nov) | Action |
|---|---|---|
| Visibility | **Private** (verified via API) | Done |
| Branch protection on `main` | Not available: the API returns *"Upgrade to GitHub Pro or make this repository public"* | Owner: upgrade the `QuantForg1` org/account to GitHub Team/Pro, then enable it on `main`: require a PR, the 7 status checks (Lint & Format, Type Check, Unit Tests, Trading Core Regression, Integration Tests, Frontend Lint Typecheck Build, Design Governance Docs) and 1 approval for `app/domain/institutional_trading/**` and `services/mt5_gateway/**` (CODEOWNERS); block force-pushes to `main` |
| Agent identity | Agents commit as the owner account | Owner: create a bot account or GitHub App with write access to `QuantForg1/QuantForg` only, and give agents that token |
| Secrets in git | None added by this program; Railway variables are listed by name only | Keep |

Until branch protection is available, every agent PR merges only after all 7 CI jobs pass (recorded in the master tracker).

## Database (Production)

- All public tables have RLS enabled. The only permissive policies are on reference data (`brokers`, `symbols`, `broker_capabilities`) and visible market-chat messages.
- Advisor findings:
  - `function_search_path_mutable` was fixed (migration `20261116115054`).
  - The three SECURITY DEFINER helpers (`current_app_user_id`, `is_org_admin`, `is_org_member`) are used by RLS policies and only return the caller's own facts. They are intended.
- API audit: path-ID routes are owner-scoped in their use cases. `/ite/research/*` had no authentication; it now requires owner/admin (#303). The billing cron secret now uses a constant-time compare (#303).
