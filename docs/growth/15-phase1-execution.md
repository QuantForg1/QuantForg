# Phase 1 execution — public guides and read-only growth status

**Date:** 19 November 2026.

## Shipped in this change

- Public guides at `/learn` and four articles: analysis versus an order, stops and the daily-loss halt, the decision record, and simulation versus broker results.
- Prices on `/learn` are read from `BILLING_PLANS`. The page states that a free trial is not offered.
- `/pricing` links to those guides.
- Sitemap and robots include `/learn`. Sitemap still omits `lastModified`.
- `/admin/growth` is a read-only owner screen. `GET /api/v1/growth/status` requires the designated owner. Every measurement value is null, with status `not_connected`, `unavailable`, or `stopped`.
- Ads kill switch in that payload is `stopped`. The endpoint does not create campaigns or query billing rows.
- `docs/saas/BILLING_AND_ENTITLEMENTS.md` now matches `start_trial` (`TRIAL_DISCONTINUED`) and `list_plans` (`trial: None`). Billing behavior was not changed.

## Not connected

Search Console, analytics, ad accounts, registration aggregates, subscriber counts, revenue, and churn. The screen says so. A sitemap URL is not treated as an indexed page.

## Still protected

No trading, risk, OMS, gateway, auth-rule, price, or entitlement change. No ads. No production secret.

## Follow-on in the same release

`/learn/decision-lifecycle` is a fifth guide. Owner-invoked checks live at `POST /api/v1/growth/automation/emergency-stop` and `POST /api/v1/growth/automation/run`. The emergency stop starts engaged, so a run does not execute until an owner releases it. Releasing it does not enable ads. Details and the tests that were actually run are in [PHASES_1_4_COMPLETION_REPORT.md](./PHASES_1_4_COMPLETION_REPORT.md).
