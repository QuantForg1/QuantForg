# 8. Pricing and subscription funnel

**Authority for what the website renders:** `frontend/src/lib/billing/plans.ts`, confirmed against https://www.quantforg.com/pricing and the homepage on 19 November 2026.  
**Billing mechanics:** `docs/saas/BILLING_AND_ENTITLEMENTS.md`, with one conflict called out below.

## Catalog

| Plan | UI price | License tier in code | Robot | Notes in the catalog |
| --- | --- | --- | --- | --- |
| No subscription | $0 | — | Cannot start. Cannot open new automated trades | Account, MT5 connect, verification, balance view, strategy and research view |
| Starter | $799 / month | `starter` | Included | 1 verified broker account, 1 active robot, email support |
| Professional | $399 / month | `professional` | Included | Marked “Most popular” in code. Priority support |
| Premium | $799 / month | `enterprise` | Included | Full eligible strategy access, premium onboarding |

Annual billing is off (`ANNUAL_BILLING_SUPPORTED` is false; the pricing page says so when that flag is false).  
Payment label: Crypto Payment.  
Access turns on only after the billing service verifies a completed payment, not when the browser returns from checkout.  
Automatic monthly crypto charging is not enabled. The customer renews with a new invoice.

`FREE_TRIAL_AVAILABLE` is `false`. The file header says there is no free trial and no free plan.

## Conflict to resolve before any campaign

`docs/saas/BILLING_AND_ENTITLEMENTS.md` still says “7-day Starter free trial (one per verified customer).” The pricing page does not offer that trial. A growth email or landing page that says “start your free trial” would be false. Update the internal doc after confirming the billing service matches `plans.ts`. This pass did not change billing.

## Feature-to-plan clarity

The comparison table is directionally honest and still vague. “Core,” “Expanded,” and “Full eligible” strategies are not defined on the page. “Essential” versus “Advanced” analytics are not defined. A buyer cannot tell what Professional adds besides the adjectives and priority support.

**Recommendation.** For each row, name the desk or the limit the entitlement actually gates, or delete the row until the gate exists. Do not invent a feature to make the columns look different. If the robot and the risk checks are identical on all paid plans, say that. Differentiation can be support and reporting only, if that is the truth.

Risk controls are “Enforced” on every paid row and “Your risk profile” when unpaid. The homepage says a subscription cannot bypass a ceiling. Keep those two sentences consistent. A plan is not a risk upgrade.

## Funnel recommendations

| Step | Keep | Change only as copy, after review |
| --- | --- | --- |
| Register | Email confirmation. About a minute, per the homepage | No pre-checked marketing consent |
| Connect broker | User types their own MT5 login. Rejected vs connected is shown | Do not ask for the login before the user chooses Broker Accounts |
| Verify | Free | Say “verification is not a subscription” |
| Choose plan | Three prices, crypto, no auto-charge | Explain renewal before the invoice, in the same words as billing |
| Pay | Server-side verified status | Do not show a paid badge on the return URL alone. The code already refuses this |
| Start robot | Explicit start | Do not auto-start after payment |
| Failed payment | Entitlement stays unpaid | Say the invoice failed and how to create another. No retry that charges a stored card, because there is no stored-card renewal |
| Cancel | Not fully specified in the public FAQ | Publish how access ends, the grace period if `BILLING_GRACE_DAYS` is real, and that open broker positions are not closed by cancellation |

## What this program will not do

- Hidden fees. The price on the card is the software price. Broker spreads and commissions are the broker’s, and the homepage already says performance includes commission and swap when it comes from broker history. Say that next to the software price so the two costs are not mixed.
- A trial that converts to a charge without a new invoice.
- Dark patterns: fake scarcity, confirm-shaming, or a plan that pretends to raise risk limits.
- A second payment ledger.

## Metrics, when billing is the source

Eligible later: invoices created, invoices finished, time from register to first finished invoice, renewals that were not replaced before expiry, entitlements expired.  
Not eligible: churn percentage, LTV, or CAC until the definitions in the architecture doc have data.  
Failed-payment and cancellation reasons need fields the billing and support services actually store. Do not add a mandatory guilt survey.
