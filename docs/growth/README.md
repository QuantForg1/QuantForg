# QuantForg Growth Program — Phase 0

**Status:** Phase 1 guides and the read-only owner status view are in the repo. See [15-phase1-execution.md](./15-phase1-execution.md).  
**Access date for external sources:** 19 November 2026.  
**Production observed:** https://www.quantforg.com  
**Code observed:** `frontend/` public routes, `frontend/src/lib/billing/plans.ts`, `app/main.py` router registry.

This folder is the Phase 0 record required before major product, marketing, or legal changes. It is research, not legal advice, and not a claim that QuantForg leads any market.

## Deliverables

| # | Document | What it decides |
| --- | --- | --- |
| 1 | [01-competitor-research.md](./01-competitor-research.md) | Who competes, on what evidence |
| 2 | [02-differentiation.md](./02-differentiation.md) | What QuantForg can own without unsupported claims |
| 3 | [03-keyword-opportunity-map.md](./03-keyword-opportunity-map.md) | Intent map. No invented search volumes |
| 4 | [04-technical-seo-audit.md](./04-technical-seo-audit.md) | Crawl, index, canonical, sitemap findings |
| 5 | [05-content-conversion-audit.md](./05-content-conversion-audit.md) | Public pages versus the requested site map |
| 6 | [06-growth-engine-architecture.md](./06-growth-engine-architecture.md) | How to measure growth without fake metrics |
| 7 | [07-automation-permission-matrix.md](./07-automation-permission-matrix.md) | Level 1 / 2 / 3 controls |
| 8 | [08-pricing-funnel.md](./08-pricing-funnel.md) | What the billing catalog actually says |
| 9 | [09-channel-strategy.md](./09-channel-strategy.md) | Channels that can be measured |
| 10 | [10-regulatory-matrix.md](./10-regulatory-matrix.md) | Country and ads restrictions. Counsel required |
| 11 | [11-roadmap.md](./11-roadmap.md) | Order of work and dependencies |
| 12 | [12-implementation-summary.md](./12-implementation-summary.md) | What changed in this pass |
| 13 | [13-test-results.md](./13-test-results.md) | What was and was not executed |
| 14 | [14-production-release.md](./14-production-release.md) | Phase 0 did not deploy |
| 15 | [15-phase1-execution.md](./15-phase1-execution.md) | Guides and read-only growth status |
| 16 | [16-measurement-sources-and-migrations.md](./16-measurement-sources-and-migrations.md) | Signed-in QA, Search Console, GA4, billing sources, activation, pending migrations |

## Baseline that later phases must not invent past

- Public indexable story is one homepage plus pricing, contact, auth, legal pages, and a public XAUUSD chart.
- Plans in the UI catalog are Starter $49, Professional $99, Premium $199 per month, paid by crypto invoice. Automatic monthly charging is off. `FREE_TRIAL_AVAILABLE` is `false` in `frontend/src/lib/billing/plans.ts`.
- The robot’s public universe is XAUUSD. Capital stays at the customer’s broker.
- Decision evidence, paper trading, execution intelligence, risk, and broker connectivity already exist as backend routers. They are frozen trading-adjacent surfaces. Growth work reads them. It does not rewrite them.
- Search Console, analytics spend, and ad accounts are not connected in this repository. Any dashboard must show “not connected” until a real source exists.
- Google’s complex-speculative policy disallows ad destinations that provide trading signals. Paid acquisition of the current robot/signal positioning is not a default channel.

## Code change in this pass

Sitemap `lastModified` no longer updates on every request. `/live` has its own canonical URL and is listed in the sitemap and robots allow list. See [12-implementation-summary.md](./12-implementation-summary.md).

## Implementation after the research pass

The research above is unchanged. Code that followed it is recorded separately, and only the items those reports list are implemented:

- [DECISION_INTELLIGENCE_COMPLETION_REPORT.md](./DECISION_INTELLIGENCE_COMPLETION_REPORT.md)
- [PHASES_1_4_COMPLETION_REPORT.md](./PHASES_1_4_COMPLETION_REPORT.md)

Search Console, analytics, subscriber counts, and paid ads remain unconnected. The owner screen says so. Document 14 is still the record that the research pass itself did not deploy.
