# 6. Growth Engine architecture

The Growth Engine is a measurement and editorial system. It is not a second trading platform and not a place that stores its own copy of orders, risk, or broker passwords.

## Principle

Every number on an owner screen has four fields stored with it: **source, date range, calculation, fetched-at.** If any field is missing, the screen shows “unavailable,” not zero. Zero is a real measurement and must not be used as a placeholder.

## What already exists and must be reused

| Need | Existing authority | Growth Engine may |
| --- | --- | --- |
| Decisions | `decision_evidence`, `decision_intelligence`, `decision_engine` routers | Read a redacted explanation for product docs. Not rewrite reasoning |
| Shadow / paper | `paper`, `quantforg_paper_trading_campaign`, shadow evaluation loop in `app/main.py` | Label simulated rows. Never add them to broker P/L |
| Risk | `risk`, `user_risk_profile` | Read limit status for an owner monitor. Not change ceilings or send orders |
| Execution quality | `execution_intelligence`, `broker_connectivity` | Read measurements the services already compute |
| Billing | `billing` router and `BILLING_PLANS` | Read invoice and entitlement state. Not grant access |
| Support | `support_desk`, `customer_operations`, `contact` | Read issue categories for owner alerts |
| Auth and roles | Existing owner/admin checks. Customers are limited to `CUSTOMER_ROUTES` | Hang owner screens on the same server-side role check |
| Public site | Next.js `app/` marketing routes | Add reviewed pages. Not a second CMS that bypasses review |

No new database of trades. If a growth table is added later, it stores content workflow and metric snapshots only.

## Funnel

The funnel is a definition, not a chart of current performance. Counts stay blank until the source column is wired.

| Stage | Definition | Allowed source | Not a source |
| --- | --- | --- | --- |
| Visitor | A request to a public URL | Analytics property, after consent | Server log guesses presented as users |
| Engaged visitor | A defined event, for example pricing view or live-chart interaction | Same property, event name documented | Scroll depth invented in the UI |
| Registration | An account row created by the auth service | Auth database aggregate, no emails in the dashboard by default | Frontend button clicks |
| Activation | A documented event. Proposed: broker connection verified, or first decision record viewed | Existing broker and product events | “Time on site” |
| Qualified | Optional later. Do not invent a score | A rule the owner writes down, with the fields it uses | A hidden model |
| Plan selection | Checkout invoice created | Billing invoices | Pricing page views |
| Paid | Invoice status that the billing service already treats as paid | Billing service | The browser return URL |
| Retained | Paid access still valid at period end | Entitlement records | A guessed churn rate |

Customer acquisition cost and lifetime value stay hidden until ad-spend records and a billing history long enough to compute them exist. The screen should say why they are hidden.

## SEO intelligence

Level 1 jobs, owner-only:

- Fetch robots and sitemap and diff them against the route list.
- Check that indexable URLs have a canonical, title, and description.
- Check that `(app)` responses stay noindex.
- List broken internal links among public pages.
- Store Search Console rows when OAuth is connected: indexed vs excluded, queries, clicks, impressions, CTR, average position, coverage errors.

The connector stores tokens in the existing secret store. Tokens are not written into the repo, chat, or client bundles.

## Content pipeline

```
topic → outline → draft → fact-check → SEO review → compliance review → approval → publish → measure → update
```

States are explicit. A draft cannot skip to publish. Financial, performance, broker, and regulatory sentences require the compliance state. The publisher is a person, or a job that refuses to run unless the approval id is present.

Automation may prepare topics, clusters, briefs, drafts, internal-link suggestions, metadata suggestions, link checks, refresh reminders, and performance notes. It may not publish those categories by itself. See [07-automation-permission-matrix.md](./07-automation-permission-matrix.md).

## Landing and acquisition

Each channel record has: audience, offer, landing path, consent basis, UTM or equivalent, conversion event, cost source or “unpaid,” compliance note, and a report date. Channels without a landing page do not get spend recommendations.

## Paid ads

Recommendations are text. Changing a budget, creating a campaign, or turning delivery on is Level 3 and defaults off. A global kill switch is a single owner control that sets “recommendations only” and, once an ad API exists, pauses delivery. Until the API exists, the switch is a documented operating rule plus a disabled client. Do not build a client that can spend.

Google’s policy is the blocker: destinations that provide signals for complex speculative products are disallowed, and forex/CFD ads need a license and certification in an eligible country. See [10-regulatory-matrix.md](./10-regulatory-matrix.md). The architecture assumes paid forex/robot ads are **off** until counsel and Google certification say otherwise.

## Subscription

Read the billing service. Do not add a second ledger. Funnel work may clarify copy. It may not add a trial, a fee, or an auto-charge that the billing service does not implement.

## Onboarding

The current public steps are the onboarding contract:

1. Create an account and confirm email.
2. Connect an MT5 login the user already has, only when they choose to.
3. Set risk, pick a plan, start the robot. Nothing trades before that start.

Extend this with read-only and paper paths that already exist. Do not add a step that submits an order.

## Owner dashboard

One owner/admin route group. Not linked from `CUSTOMER_ROUTES`. Sections can ship as empty states:

Global overview, SEO, keywords, content studio, publishing queue, channels, funnel, subscriptions, retention, feedback, campaigns, competitors, automation health, compliance, approvals, audit log.

The competitor section stores the dated notes in this folder. It does not scrape prices into a live “we are cheaper” widget.

## Automation shape

When jobs are added, use the platform’s existing scheduler and database. Required on every job: name, owner, purpose, input source, permission level, idempotency key, log, failure behavior, and a disable flag. Tenant data in any aggregate must be counts, not customer records, unless the viewer is the customer or an authorized operator under the current admin policy.

Emergency stop for growth automation: a flag that halts publish, email, and ad jobs. It must not call the trading kill switch and must not be wired into order sending.
