# 13. Test results

**Date:** 19 November 2026.

## Executed

| Check | Result |
| --- | --- |
| Production homepage fetch | https://www.quantforg.com returned the marketing page used in the content audit |
| Production `robots.txt` | Matches the repo allow/disallow list from before the `/live` allow addition |
| Production `sitemap.xml` | Eight URLs, all with `lastmod` equal to the fetch time. This is the defect the code change removes. Production will keep doing this until deploy |
| Source review of public metadata | Home, pricing, contact, privacy, terms, risk-disclosure set their own canonicals. App layout is noindex. Billing layout is noindex. `/live` did not set a canonical before this change |
| Plan catalog review | `BILLING_PLANS` prices match the positioning used in the pricing audit |
| `npm run typecheck` in `frontend/` | Exit 0 on 19 Nov 2026 (`tsc --noEmit`) |

## Not executed

ESLint, unit tests, production build, Lighthouse, link crawl, structured-data validator, and backend tests were not run. The code change is limited to sitemap and robots metadata. ESLint and the production build remain the gate before any commit or deploy of this change.

No trading-core tests were required because no trading file changed.

## How to verify the sitemap change locally

From `frontend/`, serve the app and open `/sitemap.xml`. The document should list `/live` and should not contain `lastmod` until a real edit date is added. `/live` response HTML should include a canonical link to `/live`.
