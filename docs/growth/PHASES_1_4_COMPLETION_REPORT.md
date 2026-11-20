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

As of `38f5dc8bf`, the owner HTTP surface is `GET /api/v1/growth/status` only. The earlier `POST /api/v1/growth/automation/emergency-stop` and `POST /api/v1/growth/automation/run` routes, and the screen buttons that called them, are removed. Production returns 404 for both POST paths. Nothing in the product can release the stop or start a check.

`growth_automation.py` still defaults its in-process stop to engaged and can describe catalog, index-policy, integration, and decision-contract checks. Those functions are not mounted on the API. The status document reports the stop as engaged and the scheduler as not registered. The in-process log is process memory. A restart drops it. It is not a durable audit history.

Ads stay stopped. The API has no route that enables them, changes billing, or places orders.

## Tests actually run

Rechecked on 19 November 2026 against `38f5dc8bf`:

- `ruff check` on the decision-evidence and growth modules: passed.
- `pytest tests/unit/test_decision_evidence.py tests/unit/test_growth_intelligence.py`: 19 passed. The growth router test requires GET and HEAD only.
- `learn-catalog.test.ts`, `decision-evidence.test.ts`, and `customer-routes.test.ts`: passed.

`pytest -m trading_core -q --tb=line --no-cov -p no:cacheprovider` finished with exit code 0: 2318 passed, 3328 deselected, 3 xfailed. The xfail cases are the known gold-only markers. The trading scheduler, OMS, gateway, and risk enforcement were not edited.

## Deployment

`c6953bd34` is no longer the tip. `origin/main` is `38f5dc8bf` (`fix: remove growth check controls from the owner screen`).

Vercel production deployment `https://quant-forg-5d6kvxki1-quantforg.vercel.app` (`dpl_57tTbCYJu9rE86htaBz3DQLL7Dm1`) is Ready. Its build log clones commit `38f5dc8`. It is aliased to `https://www.quantforg.com` and `https://quantforg.com`.

Unsigned checks on 19 November 2026:

| Request | Result |
| --- | --- |
| `https://www.quantforg.com/learn`, `/learn/decision-lifecycle`, `/pricing`, `/robots.txt`, `/sitemap.xml` | HTTP 200 |
| `https://quantforg.com/learn/decision-lifecycle` | HTTP 308 to `https://www.quantforg.com/learn/decision-lifecycle` |
| `GET /api/v1/decision-evidence/report` and `/history` | 401 `missing_token` |
| `GET /api/v1/growth/status` | 401 `missing_token` |
| `POST /api/v1/growth/automation/emergency-stop` and `/run` | 404 Not Found |

No designated-owner session and no paid customer session were available. Authenticated report content was not read. An HTTP 200 on `/decision-evidence` is the app shell, not a viewed decision report.

## Still blocked

| Item | Why |
| --- | --- |
| Per-user decision journal | Needs an approved append-only table. Signal history has no owner id |
| Search impressions, clicks, indexed counts | Search Console is not connected |
| Organic sessions and landing conversion | No analytics property is connected |
| Subscriber, revenue, churn, registration, activation counts | This view does not query billing rows or an event store |
| Decision Evidence view counts | No usage event is written |
| Cron on a clock | Not attached to the trading scheduler. The run routes are not mounted, so nothing is scheduled |
| Paid ads | Phase 0 restriction. The API cannot enable them |
| Authenticated production proof | No paid session was used for this report |
