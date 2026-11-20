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

## Corrected after a follow-on commit

A later commit mounted `POST /api/v1/growth/automation/emergency-stop` and `POST /api/v1/growth/automation/run`, and the owner screen gained buttons that called them. Commit `38f5dc8bf6c9a364ea9ab283daadc2cd984c9f18` removes those routes and buttons again. Growth Intelligence is `GET /status` only. Advertising stays stopped.

## Production check, 19 November 2026

Vercel deployment `dpl_57tTbCYJu9rE86htaBz3DQLL7Dm1` (`https://quant-forg-5d6kvxki1-quantforg.vercel.app`) built commit `38f5dc8` and reached Ready. Its aliases included `https://www.quantforg.com` and `https://quantforg.com`.

Unsigned HTTP checks against that alias:

- `/`, `/learn`, `/learn/analysis-versus-order`, `/learn/stops-and-daily-loss`, `/learn/decision-record`, `/learn/simulation`, `/pricing`, and `/live` returned 200. Each page’s canonical matched its own URL. `/live` is indexable.
- `/admin/growth` returned the app shell with `noindex, nofollow`.
- `robots.txt` allows `/learn` and `/live` and disallows `/admin`.
- `GET /api/v1/growth/status` on the production API returned 401 `missing_token`.
- `POST /api/v1/growth/automation/run` returned 404. No check ran.

The sitemap served by that deployment still set `lastmod` to the request time. A following commit removes `lastModified` from `sitemap.ts`. A sitemap entry is not an indexed page. No owner session was used, and the six viewports were not checked in a browser.
