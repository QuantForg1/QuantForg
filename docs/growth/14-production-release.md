# 14. Production release

**No production release was made in this pass.**

| Item | State |
| --- | --- |
| Branch deployed | None |
| Vercel deployment | Not created |
| Production sitemap | Still the pre-change file observed at 22:18 UTC on 19 Nov 2026, with per-request `lastmod` and without `/live` |
| Production homepage | Unchanged |
| Migrations | None |
| Secrets | None added or read |
| Monitoring | No new alerts |

Ship the sitemap and `/live` canonical only after the frontend gate in the repository rules is green and the diff is reviewed. Do not deploy the research markdown by itself as a product change; it is documentation and does not affect the trading service.

The ads kill switch needs nothing in production yet. There is no ad integration to turn off.
