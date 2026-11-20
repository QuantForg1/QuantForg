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
| `/learn/mt5-and-broker-history` | Broker holds the account; this page does not connect it |
| `/learn/spread-slippage-and-rejects` | Definitions only. No broker ranking and no sample rate |

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

Growth checks are not registered on the trading scheduler. That scheduler was not modified. No growth clock is attached, so nothing runs on a timer.

The emergency stop starts engaged. While it is engaged, `POST /api/v1/growth/automation/run` returns `executed: false` and `status: "stopped"`, and a draft is not saved. Releasing the stop allows one owner to request a check or save an unpublished draft. Releasing it does not enable ads, change billing, or place orders.

Owner routes, all behind the designated-owner role:

- `GET /api/v1/growth/status`
- `POST /api/v1/growth/automation/emergency-stop`
- `POST /api/v1/growth/automation/run`
- `POST /api/v1/growth/content/drafts`
- `POST /api/v1/growth/content/publish` — always returns `published: false` and `status: "approval_required"`

Checks: catalog prices (subscriber count null), declared index policy (indexed count null), integration sources, decision-evidence contract, SEO contract (search volume null), and labeled hypotheses (`proven_outcome: false`). A completed check replays inside the same UTC minute. An unknown job returns 422. There is no retry. The log and drafts live in process memory and are dropped on restart.

Ads stay stopped. There is no route that enables them.

## Tests actually run

For this change, on 19 November 2026:

- `poetry run pytest tests/unit/test_growth_intelligence.py -o addopts=`: 6 passed. Covers null metrics, owner 403s, stop-before-run, catalog prices with a null subscriber count, idempotent replay, null search volume, unknown job 422, unpublished drafts, publish refusal, and the stop blocking a later draft.
- `learn-catalog.test.ts`: passed. Seven guides, no `lastModified:` assignment, no profit or trial-available language.

`pytest -m trading_core` was not re-run for this change. The trading scheduler, OMS, gateway, and risk enforcement were not edited.

## Deployment

The production alias before this change served commit `8121d6840`. Deployment of the commit that adds the guides, onboarding steps, and owner checks is recorded after that Vercel deployment is Ready. Until then, do not treat this file as proof that those routes are live.

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
| Cron on a clock | Not attached. Owner-invoked checks exist. Nothing runs unattended |
| Paid ads | Phase 0 restriction. The API cannot enable them |
| Authenticated production proof | No paid session was used for this report |
