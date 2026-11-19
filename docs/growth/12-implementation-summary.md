# 12. Implementation summary

**Date:** 19 November 2026.  
**Scope obeyed:** Phase 0 before major product, marketing, or legal changes. Trading core, OMS, gateway, risk math, auth protections, billing behavior, and design-system components were not modified.

## Research

Documents 01 through 11 and 13 through 14 in this folder. External pages were fetched on 19 November 2026. Prices that did not appear on an official page are marked secondary or omitted. Search volumes were not invented. No testimonials, rankings, or performance figures were created.

## Product code

| File | Change |
| --- | --- |
| `frontend/src/app/sitemap.ts` | Removed per-request `lastModified`. Added `/live`. Login priority set to 0.5 so it sits below register and the product pages |
| `frontend/src/app/live/layout.tsx` | Canonical `/live` and Open Graph URL, so the public chart is not a duplicate of the homepage |
| `frontend/src/app/robots.ts` | Explicit allow for `/live` |

## Not built, on purpose

- Owner dashboard. It would show empty metrics and invite fake numbers. The architecture says to build it when a source is connected, with “unavailable” as the empty state.
- New marketing pages. They need the copy review in the roadmap. The homepage already carries the claims; duplicating them unreviewed would be a major marketing change.
- Search Console, analytics, email, and ad clients. No secrets were requested or added.
- Programmatic pages. The spam policy and the thin-content risk make a generator the wrong first move.
- Any change under the trading-core freeze.

## Production

The live sitemap still has request-time `lastModified` until a deployment. This pass did not deploy. See [14-production-release.md](./14-production-release.md).
