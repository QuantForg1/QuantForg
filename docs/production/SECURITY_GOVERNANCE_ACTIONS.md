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

## Branch protection plan (requires a plan upgrade)

`QuantForg1` is a **user** account, and the repository is private. GitHub only offers branch protection and rulesets on private repositories with **GitHub Pro** (user) or Team/Enterprise (organization). The API currently answers 403: *"Upgrade to GitHub Pro or make this repository public"*.

After upgrading, run this from any machine with `gh` signed in as the owner:

```bash
gh api -X PUT repos/QuantForg1/QuantForg/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": {"strict": true, "contexts": [
    "Lint & Format", "Type Check", "Unit Tests", "Trading Core Regression",
    "Integration Tests", "Frontend Lint Typecheck Build", "Design Governance Docs"]},
  "enforce_admins": false,
  "required_pull_request_reviews": {"required_approving_review_count": 1,
    "require_code_owner_reviews": true, "dismiss_stale_reviews": true},
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": true
}
JSON
```

- `.github/CODEOWNERS` already maps every risk, execution, gateway, vault, worker, migration and CI path to the owner, so owner review is enforced on those paths.
- `enforce_admins: false` lets the owner merge in an emergency.
- The agent bot identity (section above) must **not** be an admin, so its PRs always need the 7 checks and owner review on CODEOWNERS paths.
