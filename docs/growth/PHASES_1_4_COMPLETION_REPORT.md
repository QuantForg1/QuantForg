# Phases 1–4 completion report

**Date:** 19 November 2026.  
**Scope:** public education, owner growth status, owner-invoked checks, and the existing billing catalog.  
**Not in scope:** trading engines, billing prices, entitlements, payment capture, ads spend, Search Console, analytics, and production schema changes.

Phase 0 research in this folder stays as the research record. This file records what was implemented after it.

## Phase 1 — Education

Public guides in `frontend/src/lib/marketing/learn-catalog.ts`:

| Path | Subject |
| --- | --- |
| `/learn/analysis-versus-order` | Analysis, intention, risk check, and an order are different events |
| `/learn/stops-and-daily-loss` | Protective stop and daily-loss halt, and what they do not guarantee |
| `/learn/decision-record` | Decision record versus a broker fill |
| `/learn/decision-lifecycle` | BUY, SELL, WAIT, ORDER_SENT, FILLED, NOT_REACHED, and thinner history |
| `/learn/simulation` | Simulation is not broker performance |

Copy is original and matches the implemented report. The catalog test rejects guaranteed-profit language, win-rate claims, percentage figures, and “free trial is available”.

`docs/saas/BILLING_AND_ENTITLEMENTS.md` was aligned to the code: Starter $49, Professional $99, Premium $199 from `plans_public()`, `FREE_TRIAL_AVAILABLE` false, `start_trial` raises `TRIAL_DISCONTINUED`. Billing code was not changed.

Get Started links to `/learn/decision-lifecycle`. That step has no checklist id, so it does not change onboarding completion math and does not record a fake activation event.

## Phase 1 — Growth Intelligence

`GET /api/v1/growth/status` is owner-only. A trader and a non-designated owner receive 403. The designated owner receives 200.

Every unconnected metric has `value: null`. Status words used:

- `not_connected` — Search Console, analytics, acquisition
- `unavailable` — content conversion, subscriber counts, revenue, churn, registrations, activation, Decision Evidence views
- `stopped` — ads and growth automation

The page is `/admin/growth`. It prints those words. It does not print sample traffic or revenue. Catalog prices come from `plans_public()` and are labelled as software prices, not subscriber counts.

Decision Evidence usage stays unavailable. There is no event store. A route request is not stored as a viewed report.

## Phase 2 — Organic

- Sitemap lists `/`, `/pricing`, `/live`, `/learn`, each guide, contact, login, register, and legal pages. Authenticated desks are absent. `lastModified` is not emitted on each request.
- `robots.ts` allows those public paths and disallows product desks, including `/decision-evidence`, `/signals`, and `/ai-trading-intelligence`.
- `/live` keeps its own canonical and Open Graph URL.
- Each guide sets its own canonical and Open Graph URL and emits Article plus FAQ structured data.
- Guides link to each other, to pricing, to the risk disclosure, and to contact.
- Indexed-page counts, impressions, clicks, and rankings are not stored. The owner view says Search Console is not connected.

## Phase 3 — Activation and retention

Onboarding copy explains the product, the MT5 XAUUSD focus, the broker relationship, decision words, risk checks, and subscriptions. It does not connect a broker and does not ask for a broker password.

No activation rate is calculated. Observable events that are not instrumented stay uncounted. Incomplete onboarding still uses the existing local checklist. Retention mail was not added. There is no mass communication path in this change.

Plan prices and entitlements on the pricing page are the existing catalog. No charge, invoice, or price edit was made.

## Phase 4 — Automation

Growth checks are not registered on the trading scheduler. That scheduler was not modified.

Owner routes, in addition to the status GET:

- `POST /api/v1/growth/automation/emergency-stop` with `{ "engaged": true | false }`
- `POST /api/v1/growth/automation/run` with `{ "job_id": "..." }`

The emergency stop starts engaged. A run while it is engaged returns `executed: false` and `status: "stopped"` and does not call the check. Releasing the stop does not enable ads, change billing, or place orders. There is no job id that turns ads on. An unknown job returns 422.

Checks that can run after a release:

| Job | What it returns |
| --- | --- |
| `catalog_prices` | Prices from `plans_public()`. `subscriber_count` is null |
| `public_route_policy` | The declared indexable and noindex paths. `indexed_page_count` is null |
| `integration_sources` | Search Console and analytics `not_connected`. Ads `stopped`. Counts null |
| `decision_evidence_contract` | The read-only flags from `evidence_contract()`. Usage events null |

A completed check is replayed for the same job in the same UTC minute (`idempotent_replay`). A failed check is not retried. The timeout budget is 2 seconds. The log is process memory: a restart engages the stop and drops the log. The owner page states that.

## Tests actually run

- `pytest tests/unit/test_decision_evidence.py tests/unit/test_growth_intelligence.py`: 21 passed. Coverage includes null metrics, trader and non-designated-owner 403, designated-owner 200, stop-before-run, catalog prices equal to `plans_public()`, idempotent replay, unknown job 422, and stop-after-release.
- `ruff check` on the growth and decision-evidence modules: passed.
- `learn-catalog.test.ts`, `decision-evidence.test.ts`, `customer-routes.test.ts`: passed.

`pytest -m trading_core` was not run. Frozen trading modules were not edited.

## Deployment

`origin/main` includes `091ab3f9bac3a06d13ed48f11aa7ce56ec6c1c78` (`fix: export the decision evidence API client`), on top of `d2e128f6f` (owner growth checks restored) and `1ac16995e` (the decision-intelligence commit).

Vercel production deployment `https://quant-forg-h96kevlwn-quantforg.vercel.app` is Ready and aliased to `https://www.quantforg.com`, `https://quantforg.com`, and `https://quant-forg-git-main-quantforg.vercel.app`.

Public checks, unsigned:

| Request | Result |
| --- | --- |
| `/learn`, `/learn/decision-lifecycle`, `/pricing`, `/robots.txt`, `/sitemap.xml` | HTTP 200 |
| `/learn/decision-lifecycle` body | States that ORDER_SENT is not a fill and NOT_REACHED is not a pass |
| `/decision-evidence` | HTTP 200 app shell, `noindex` |
| `robots.txt` | Allows `/learn`. Disallows `/decision-evidence` |
| Sitemap | Contains `/learn/decision-lifecycle` |
| `GET /api/v1/decision-evidence/report` | 401 `missing_token` |
| `GET /api/v1/growth/status` | 401 `missing_token` |
| `POST /api/v1/growth/automation/emergency-stop` | Route exists. An unsigned call did not execute a check |

No designated-owner session and no paid customer session were used. Authenticated report content, owner controls, and a viewed decision report were not demonstrated in production.

`pytest -m trading_core` was not run. This change does not modify the trading scheduler, OMS, gateway, or risk enforcement.

## Still blocked

| Item | Why |
| --- | --- |
| Per-user decision journal | Needs an approved append-only table. Signal history has no owner id |
| Search impressions, clicks, indexed counts | Search Console is not connected |
| Organic sessions and landing conversion | No analytics property is connected |
| Subscriber, revenue, churn, registration, activation counts | This view does not query billing rows or an event store |
| Decision Evidence view counts | No usage event is written |
| Cron on a clock | Not attached to the trading scheduler. Checks run only when an owner requests them and the stop is released |
| Paid ads | Phase 0 restriction. The API cannot enable them |
| Authenticated production proof | No paid session was used for this report |
