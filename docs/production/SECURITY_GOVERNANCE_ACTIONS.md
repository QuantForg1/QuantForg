# Security and governance: owner actions (16 Nov 2026)

## Supabase: Leaked Password Protection (security advisor WARN)

Source: Supabase docs, "Password security" (https://supabase.com/docs/guides/auth/password-security), checked on 16 Nov 2026.

- Supabase Auth checks passwords against the HaveIBeenPwned Pwned Passwords API and rejects ones that are known to have leaked.
- **This requires the Supabase Pro plan or above.** The QuantForg organization is already on **Pro** (verified 16 Nov via the Supabase API, `plan: pro`), so no upgrade is needed. Only the toggle is missing.
- The setting lives on the project's **Auth settings → Providers → Email** page: `https://supabase.com/dashboard/project/otqyhlmwaifokrczryrc/auth/providers?provider=Email`.

Steps (owner):
1. Open the link above, then turn on **Prevent use of leaked passwords**.
2. On the same page, set the minimum password length to 10 or more and require digits, lowercase letters, uppercase letters and symbols.
3. Save, then re-run the security advisor. The finding `auth_leaked_password_protection` should be gone.

Effect: new sign-ups and password changes must meet the rules. Existing users keep signing in, but a weak password raises `WeakPasswordError` at sign-in, which tells them to change it. Make sure the sign-in UI shows that message.

The agent cannot change this project setting, so the owner must do it.

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
