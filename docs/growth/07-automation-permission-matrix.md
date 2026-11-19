# 7. Automation permission matrix

Levels match the program. A job’s level is the highest-risk action it can take, not the action it usually takes.

**Level 1 — automatic.** Read, classify, report, recommend.  
**Level 2 — prepare, then a named person approves.**  
**Level 3 — blocked until a specific owner authorization for that action.** Default is off.

The trading kill switch, OMS, gateway, and risk engine are not in this matrix. Growth jobs must not call them.

| Action | Level | May run unattended | Approval | Rollback |
| --- | --- | --- | --- | --- |
| Diff robots.txt and sitemap against the repo | 1 | Yes | None | Disable the job |
| Fetch public page metadata and status codes | 1 | Yes | None | Disable the job |
| Store Search Console or analytics rows after OAuth | 1 | Yes, read-only scopes | Owner connects the account once | Revoke OAuth |
| Keyword list from Search Console queries | 1 | Yes | None | Delete the snapshot |
| Broken-link report on public URLs | 1 | Yes | None | Disable the job |
| Draft a glossary page from an approved outline | 1 to prepare | Draft only | Level 2 to publish | Unpublish |
| Suggest title, description, internal links | 1 | Yes, suggestions | A person accepts them | Revert the page |
| Refresh reminder when a page’s sources age | 1 | Yes | None | Dismiss |
| Publish a non-financial docs typo fix | 2 | No | Editor | Git revert |
| Publish any page that mentions performance, brokers, risk outcomes, or regulation | 2 | No | Editor plus compliance reviewer | Unpublish and correct |
| Send a consented product email to existing subscribers | 2 | No | Owner, and a lawful basis recorded | Stop the send; do not scrape lists |
| Change public pricing copy | 2 | No | Owner. Copy must match `plans.ts` and the billing service | Revert |
| Change a plan price, trial, or entitlement | 3 | No | Owner, and a billing change in the billing service | Billing rollback plan, separate review |
| Create or edit an ad campaign, budget, or bid | 3 | No | Owner, plus country eligibility and Google certification where required | Global ads kill switch |
| Spend money | 3 | No | Owner for that amount | Platform pause |
| Connect a broker, change a user, or reveal a secret | 3 | No | Existing auth and broker flows only | Existing disconnect and secret rotation |
| Place, modify, or cancel an order | Forbidden | Never | Not a growth action | Trading runbooks, not this system |
| Weaken a risk limit or skip a stop | Forbidden | Never | Not available | — |
| Buy or rent a contact list, or message people who did not consent | Forbidden | Never | — | — |
| Publish a testimonial, user count, award, or profit figure | Forbidden unless evidence and permission are attached to the approval | Never automatic | Owner plus the evidence file | Remove the page |

## Record every run

| Field | Required |
| --- | --- |
| Job name | Yes |
| Level | Yes |
| Actor | System or user id |
| Purpose | Yes |
| Inputs | Source ids, not raw secrets |
| Output | Report id or pull request |
| Started, finished, error | Yes |
| Approval id | Required for level 2 and 3 |

## Kill switch

One owner-only control: **Growth automation: stopped.**

When stopped, Level 1 reports may still be read, and no job may publish, email, or call an ad API. The control is independent from the trading emergency stop. Stopping growth must not flatten positions or start them.

## Data

- Public pages: no customer positions, emails, or account numbers.
- Owner aggregates: counts and rates.
- Support text: visible to existing support roles only.
- Retention: metric snapshots follow the company’s existing data-retention rules. Do not create a longer private archive as a side effect of SEO.

This matrix is an operating design. The jobs in the Level 1 column are not all built yet. See [12-implementation-summary.md](./12-implementation-summary.md).
