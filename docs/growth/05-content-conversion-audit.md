# 5. Website content and conversion audit

**Observed:** https://www.quantforg.com on 19 November 2026, plus `frontend/src/app/page.tsx`, `pricing/page.tsx`, legal pages, and `frontend/src/components/marketing/home-landing.tsx` references in the fetched copy.

## What a visitor can open without an account

| URL | Role today | In sitemap before this pass |
| --- | --- | --- |
| `/` | Full product story, brokers, steps, risk ceilings, plan teaser, FAQ | Yes |
| `/pricing` | Starter, Professional, Premium from `BILLING_PLANS` | Yes |
| `/live` | Public XAUUSD chart and discussion. Not a broker login | No |
| `/contact`, `/contact/success` | Contact | `/contact` yes |
| `/login`, `/register` | Account creation | Yes |
| `/privacy`, `/terms`, `/risk-disclosure` | Legal. Updated date on the pages: 8 November 2026 | Yes |
| `/purchase` | Redirects to `/contact` | No |

There is no public URL dedicated to platform overview, AI behavior, strategies, signals, risk, broker measurement, security, documentation, about, or FAQ as its own document. The homepage contains short versions of several of those. One long homepage cannot rank or convert for each job.

Authenticated desks such as `/decision-evidence`, `/research`, and `/ai-trading-intelligence` are the product. They are noindex and must stay noindex. Public pages should describe them without dumping a customer’s records.

## Homepage content versus the required questions

| Question | Answer on the homepage today | Gap |
| --- | --- | --- |
| What it does | MT5 intelligence, gold robot, assistant, chart screenshots | Split into scannable pages so each claim has room for limits |
| Who it is for | Implied: someone with an MT5 account who wants gold automation | Say this in one paragraph, including who it is not for |
| How it works | Eight stages from scan to broker history | Good. Keep this as the canonical process description |
| What data it uses | Live gold market, chart image the user supplies, broker history | Name freshness and failure: unread chart, lost connection |
| What it does not do | Does not custody funds, does not guarantee profit, does not trade until the user starts it | Repeat on every commercial page |
| Limitations | Gaps can exceed a planned loss. Quiet markets mean no trade. XAUUSD only | This is the best trust copy on the site. Do not soften it |
| Subscription | Teaser of three plans. Robot needs an active subscription. Crypto payment. No automatic monthly charge | Pricing page is the catalog. Homepage must not drift from `plans.ts` |
| Next action | Create account, open broker accounts, review controls | Broker-account link is an authenticated destination. Logged-out visitors need register first, which the first step already says |

## Conversion facts, not opinions

- **Price is visible** on `/pricing`: $199, $399, $799 per month in `plans.ts`.
- **Unpaid value is visible:** create account, connect MT5, verify, view balance and research. Start robot and new automated trades require a subscription.
- **Payment friction is explicit:** crypto invoice, access only after a verified completed payment, renew with a new invoice. That will suppress impulse checkout. Hiding it would be a dark pattern. Explain it earlier, do not remove it.
- **No trial in the catalog.** `FREE_TRIAL_AVAILABLE` is `false`. `docs/saas/BILLING_AND_ENTITLEMENTS.md` still describes a 7-day Starter trial. The rendered site follows the code, not that older doc. Reconcile the doc before anyone writes “free trial” in marketing.
- **“Most popular”** is hardcoded on Professional (`highlighted: true`). That is a merchandising label, not usage data. Acceptable if it stays a design choice. Do not attach a fake percentage of customers.
- **Social proof is absent.** Correct. Do not add testimonials, user counts, or profit screenshots.
- **Broker logos are names.** Weltrade, XM, Exness, HFM, JustMarkets, IC Markets, Pepperstone, FP Markets. Confirm each name is still a supported connection before a new campaign repeats the list. Do not imply the broker endorses QuantForg.
- **Privacy names NOWPayments.** The billing UI is required to hide the processor brand (`plans.ts` comment and `docs/saas/BILLING_AND_ENTITLEMENTS.md`). The privacy page is the legal disclosure. Do not “fix” that by editing legal text in a growth pass. Counsel should decide whether the customer UI and the policy need to match.

## Calls to action that are already honest

Keep these sentences. They are the conversion policy:

- Software access is not a promise of trading profits.
- Nothing trades until the user starts the robot.
- A failed risk check means no trade.
- Results come from the broker’s history.

## Pages to add later, and only as explanations

Use the existing pricing chrome and RC4 tokens. One primary action: create an account, or open pricing. No countdown, no “seats left.”

1. Platform — the eight stages, with the four boundary lines.
2. Decisions — record shape, link to sign-in, no sample ticket.
3. Risk — ceilings versus preferences, gap risk.
4. Brokers — how a connection is verified, no quality ranking.
5. Security — encryption, isolation, and audit logging already described on the homepage, plus what is not certified.
6. Documentation index — the ten first-wave topics in the keyword map.
7. About and support — who operates the service and how to contact them. About must not invent a team, a license, or an office address the company has not published. The homepage structured data uses support@quantforg.com. Confirm that mailbox before relying on it in ads. Google’s financial-products disclosure rules require a physical address on ad destinations; the captured homepage did not show one.

## What not to ship

- A blog of 100 generated gold articles.
- Comparison pages that score brokers or competitors on profit.
- A public leaderboard of customer accounts.
- Any restyle of Terminal, Book, Research, or Counsel. The design system is frozen.
