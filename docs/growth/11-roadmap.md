# 11. Roadmap

Dependencies run downward. A later row does not start by editing the trading core. Frozen modules stay frozen unless a separate, named approval says otherwise.

## Now — done in this pass

| Item | Dependency | Outcome |
| --- | --- | --- |
| Phase 0 research | Production site and official competitor and policy pages | This folder |
| Stop false sitemap freshness | None | `sitemap.ts` no longer emits `new Date()` |
| Give `/live` its own canonical | None | Layout canonical, sitemap, robots allow |

## Done — Phase 1

| Item | Outcome |
| --- | --- |
| Public guides | `/learn` and four articles, canonicals, sitemap, footer and header links |
| Trial documentation | `docs/saas/BILLING_AND_ENTITLEMENTS.md` matches the discontinued trial |
| Owner growth status | `GET /api/v1/growth/status` and `/admin/growth`. Metrics without a source are null |

## Next — still no trading edits

| Priority | Item | Depends on | Done when |
| --- | --- | --- | --- |
| P0 | Counsel memo for UK, US, AU, and any country the owner wants to target | This matrix | A yes/no for organic promotion and a separate yes/no for ads |
| P1 | Make plan comparison rows name real gates or remove them | Entitlement code | Pricing page matches what a Starter account can open |
| P1 | Search Console and privacy-safe analytics, read-only | Counsel on cookies, owner OAuth | Owner view shows source, range, calculation, fetched-at, or “not connected” |
| P2 | Level 1 auditor: sitemap, canonicals, noindex on app layouts, broken public links | The public page set | A report artifact, not a redesigned site |
| P2 | Decision-record explainer inside the existing decision evidence desk | The existing API | Fields the API does not return render as unavailable |
| P2 | Shadow results labeled and excluded from broker P/L totals | Existing paper and shadow services | A test that a simulated row cannot be summed into live P/L |

## Later — owner approval on each row

| Item | Level | Blocker |
| --- | --- | --- |
| Publishing queue for the editorial states | 2 | Reviewer roles |
| Consented newsletter | 2 | Consent storage and unsubscribe |
| Broker measurement page inside the product | 1 to display | Enough comparable fills. No public ranking before that |
| Ad recommendations | 1 | A real ad account export. No API that can change budgets |
| Ad delivery | 3 | Certification, country memo, kill switch, spend approval |
| Locale sites | 2 | Maintainer for that language plus the country memo |
| Referrals or affiliates | 3 | Contract, disclosure, billing that can express a credit without touching orders |

## Explicitly out of roadmap until a trading-core approval

New strategies, threshold changes, OMS or gateway changes, risk-ceiling changes, kill-switch changes, and any job that places an order or rewrites a live parameter.

## Success standard for the next quarter

Not a rank and not a revenue target pulled from nothing.

- Every public commercial page states what the software does not do.
- Every owner metric that is shown can be recalculated from a named source.
- No page claims a profit, a user count, or a broker ranking.
- A person can read a decision and see which checks failed.
- Simulated and broker P/L cannot be mixed by the UI.
