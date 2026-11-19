# 4. Technical SEO audit

**Property:** https://www.quantforg.com  
**Code:** `frontend/src/app/sitemap.ts`, `frontend/src/app/robots.ts`, `frontend/src/app/layout.tsx`, public page metadata.  
**Fetched:** 19 November 2026.

Search Console was not available. Indexed-page counts, coverage errors, impressions, and Core Web Vitals field data are therefore **unknown**. This audit is source plus the live robots and sitemap responses. It is not a crawl of every URL and not a Lighthouse run.

## What is in good shape

| Check | Evidence |
| --- | --- |
| HTTPS production host | https://www.quantforg.com returned the marketing page |
| `metadataBase` | Root layout uses `NEXT_PUBLIC_APP_URL` or https://www.quantforg.com |
| Homepage title and description | Specific, and they disclaim profit promises |
| Homepage canonical | `alternates.canonical: "/"` |
| Pricing, contact, privacy, terms, risk canonicals | Each sets its own path |
| Open Graph image | `/og-image.png` 1200×630 referenced on home, pricing, contact |
| Authenticated app | `(app)/layout.tsx` sets `robots.index: false` and `follow: false` |
| Billing routes | `billing/layout.tsx` noindex |
| Robots sitemap pointer | Live `robots.txt` points at https://www.quantforg.com/sitemap.xml |
| Structured data | `PublicStructuredData` emits Organization, WebSite, and SoftwareApplication. Offers use the real plan prices. No aggregate rating |
| Self-hosted fonts | IBM Plex via `next/font/local`, which avoids a Google Fonts fetch |

## Defects

### 1. Sitemap `lastModified` was “now” — fixed in this pass

`sitemap.ts` set `lastModified: new Date()` for every URL. The live sitemap fetched on 19 Nov 2026 showed `2026-11-19T22:18:35.715Z` on all eight URLs, which is the request time, not an edit time. Google uses `lastmod` as a change hint. A fresh timestamp on every fetch trains the crawler to ignore it.

**Change:** `lastModified` is omitted until a page’s content actually changes.

### 2. `/live` was indexable and canonicalized to the homepage — fixed in this pass

`/live` is a public XAUUSD chart (`frontend/src/app/live/page.tsx`). Its layout set `index: true` and did not set a canonical. The root layout’s `alternates.canonical` is the site origin, so a child that does not replace `alternates` can advertise the homepage as its canonical. The URL was also missing from the sitemap while remaining crawlable (`Allow: /`).

**Change:** `/live` now has canonical `/live`, an Open Graph URL, a sitemap entry, and an explicit robots allow.

### 3. Robots disallow list does not name the app

`robots.txt` disallows `/dashboard`, `/admin`, `/research`, `/broker`, and a short list of desks. The app has on the order of 300 pages. HTML noindex on `(app)/layout.tsx` is the control that matters. Disallow does not stop indexing of a URL that gets linked. Keep noindex on every authenticated layout. Do not “fix” this by pasting 300 disallow lines.

`/purchase` redirects to `/contact` and is not in the sitemap. Leave it as a redirect.

### 4. Login and register are in the sitemap

That is acceptable for brand navigational queries. They should not be the target of educational content.

### 5. No field performance data

Page speed, LCP, INP, and CLS were not measured in this pass. Do not claim Core Web Vitals scores. A later Level 1 job can store Lighthouse or CrUX results with the URL, date, and source.

### 6. International SEO is not implemented

`openGraph.locale` is `en_US`. There is no `hreflang`. That is correct until a second language is maintained.

### 7. Structured data scope

Offers are accurate. There is no `Review` or `AggregateRating`, which is correct because no verified review corpus exists. Do not add star ratings. `sameAs` is empty. Add profile URLs only when the accounts exist and are official.

## Live files observed

- https://www.quantforg.com/robots.txt
- https://www.quantforg.com/sitemap.xml (before the `lastModified` fix; production still serves the old file until a deploy)

## Not checked

Broken-link crawl, duplicate-content hash, image byte size, mobile usability in a browser session, and redirect chains beyond `/purchase`. Those are Level 1 jobs for the growth engine once an owner turns the auditor on. They were not invented here.
