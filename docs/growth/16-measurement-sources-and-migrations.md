# Measurement sources, signed-in QA, and pending migrations

**Date:** 20 November 2026.  
**Code baseline:** `05e0c9fe41bc523400cc23a93cad4534061bed9b`.  
**Status:** documentation only. No migration was applied. No credential was added. No Growth control route was mounted.

This file records what the repository can support today and what still needs a separate owner approval. It does not report subscriber counts, revenue, churn, search traffic, or activation totals.

## 1. Signed-in browser QA

These checks were not run. No paid, unpaid, or owner session was available. Unsigned production checks already show:

- `GET /api/v1/decision-evidence/report` and `/history` return 401 `missing_token`.
- `GET /api/v1/growth/status` returns 401 `missing_token`.
- `POST /api/v1/growth/automation/run`, `/automation/emergency-stop`, `/content/drafts`, and `/content/publish` return 404.
- `/decision-evidence` and `/admin/growth` return the app shell with `noindex`. An HTTP 200 shell is not a viewed report.

Use a normal browser. Do not paste tokens into chat or into the repository. Do not place an order, change a position, release the growth stop, or start a check.

### Unauthenticated

1. Open a private window.
2. Open `https://www.quantforg.com/decision-evidence`. Expect the sign-in shell, not a decision report.
3. Open `https://www.quantforg.com/admin/growth`. Expect the same shell, not owner metrics.
4. The network call to the report and growth status APIs should be 401.

### Unpaid customer

Sign in as a customer whose `public.licenses` row is missing, not `active`, or past `expires_at`. `require_signals_subscription` checks the role first, then `check_trading_entitlement`. An unpaid customer is not an owner bypass.

1. Open `/decision-evidence`.
2. Expect the subscription wall. The API should return 402 `subscription_required`.
3. Open `/admin/growth`. Expect 403. An ordinary customer must not see owner status.
4. Confirm the page does not show another customer’s signal, order, or account.

### Paid customer

Sign in as a customer with an active, unexpired license and the `signals` feature still allowed.

1. Open `/signals`, then **Decision evidence**.
2. If the feed is empty, the copy must stay “Awaiting engine evidence”. That is not a failed test.
3. If a live row is present, confirm `ORDER_SENT` is not labeled filled, `NOT_REACHED` is not labeled passed, and missing history fields stay unavailable.
4. A history row must show the history note. The current quote must not fill a blank historical spread, ATR, risk limit, or ticket.
5. Sign out and sign in as a second paid customer. The report is a shared signal projection, not a private journal. It must not show the first customer’s broker password, account number, or invoice.

### Designated owner

`require_roles` treats an owner or admin whose email is not the designated owner as a trader. Only the designated owner should open Growth Intelligence.

1. Sign in as that owner.
2. Open `/admin/growth`.
3. Expect “Not connected”, “Unavailable”, or “Stopped”. Catalog prices are software prices, not revenue.
4. Confirm there is no Release stop, Run check, or Save draft control.
5. The ads line stays Stopped.
6. Sign in as any other owner or admin. `/admin/growth` and `GET /api/v1/growth/status` should be 403.

## 2. Google Search Console

There is no Search Console data client in this repository.

What exists is unrelated to query and index metrics:

- Customer Google sign-in uses Supabase OAuth (`GET /api/v1/auth/oauth/google`). That consent is for login. It is not a Search Console grant.
- `docs/auth/GOOGLE_OAUTH_SETUP.md` describes DNS verification of `quantforg.com` so Google OAuth branding can show the domain. A verified domain is not a connected Search Console property and does not return impressions, clicks, or indexed-page counts.

What is missing before any metric can be shown:

1. A Google account that is an Owner of a Search Console property for `quantforg.com` or `https://www.quantforg.com/`.
2. The Search Console API enabled on a Google Cloud project.
3. An OAuth client, or a restricted service account, whose only scope is `https://www.googleapis.com/auth/webmasters.readonly`. Do not reuse the customer login client, and do not add that scope to customer sign-in.
4. One owner consent. Store the refresh token only in the Railway secret store. Do not commit it and do not put it in `NEXT_PUBLIC_*`.
5. The property URL recorded as configuration, not guessed at read time.
6. An owner-only read path. The current Growth screen must keep saying “Not connected” until a response includes the property, the date range, and the fetch time.

No historical Search Console rows exist here, so nothing can be backfilled.

## 3. GA4

No GA4 property, measurement ID, gtag snippet, or Analytics Data API client is configured. A repository search finds no measurement ID and no analytics setting.

What a later connection would require:

1. A GA4 property and a web stream whose default URL is `https://www.quantforg.com`.
2. The measurement ID supplied as configuration for the public snippet only. The reporting property number is separate and stays server-side.
3. A consent choice before the snippet loads. The snippet must not send broker account numbers, order tickets, signal payloads, prices of open positions, or tokens.
4. For owner reports, the Analytics Data API with `analytics.readonly`, an owner-only credential in Railway, and a recorded property id. A public measurement ID cannot by itself produce owner session or conversion totals.
5. Until that response exists, organic sessions and landing conversion stay “not connected” or “unavailable”. Do not estimate them from page templates or from HTTP access logs.

## 4. Billing sources for subscribers, revenue, and churn

The Growth status document does not query billing tables. Catalog prices in `plans_public()` are software prices. They are not subscribers or revenue.

Tables that already exist:

| Source | Useful columns | What it can support later | What it cannot support |
| --- | --- | --- | --- |
| `public.licenses` | `user_id`, `tier`, `status`, `issued_at`, `expires_at`, `revoked_at` | A paid subscriber is an `active` license whose `expires_at` is null or in the future, with tier `starter`, `professional`, or `enterprise`. Premium invoices are stored as enterprise licenses. | A count was not calculated. Trial rows are not paid subscribers. `check_trading_entitlement` does not treat an active trial as a license. |
| `public.billing_orders` | `user_id`, `plan_id`, `amount_usd`, `status`, `paid_at`, `period_start`, `period_end`, `cancelled_at` | Cash collected is the sum of orders that reached a paid status with `paid_at` set, excluding `refunded`, `partially_paid`, and unpaid `pending_payment`. | This is not processor MRR. Invoices are one-time crypto invoices. Automatic monthly charging is off. A pending invoice is not revenue. |
| `public.billing_trials` | `user_id`, `status`, `expires_at` | Historical trial rows may exist. | New trials are discontinued. A trial is not revenue and not a paid subscriber. |
| `public.billing_webhook_events` | provider payload | Idempotency of payment notices. | Not an analytics table. Authenticated clients cannot read it. |

Churn is not a column. A later definition that matches this schema is: a user who had an active unexpired license at the start of a stated window and has no active unexpired license at the end, after ignoring `renewal_due` and `past_due` until the license actually expires or is revoked. That rate was not computed. `billing_orders` lets a customer read only their own rows. An owner total would have to go through the service role and the designated-owner check. It must not be added to the customer API.

## 5. Activation

Activation is not an HTTP request, a catalog price, or a local checklist tick.

Two different facts have to stay separate:

- **Paid access started.** This can later be read from `licenses` and `billing_orders.paid_at`. It is payment, not activation. It was not aggregated in this pass.
- **Customer activated.** The first time, after paid access has started, the same user receives a recorded `decision_evidence_rendered` event. That event does not exist. It would be written only after the signed-in client has rendered a report body, with `user_id`, the report source id, and `rendered_at`. The same user and source id must not insert a second row. The payload must not include broker secrets, order bodies, or raw signal text.

The Get Started checklist is `localStorage` on that browser. It is not an activation event and it cannot be summed across customers.

No historical activation number can be reconstructed. Paid license rows are not a substitute for the missing render event.

## 6. Proposed migration: `decision_journal_entries`

Not approved. Do not run this against production until the owner accepts the schema and the retention period.

Signal history has no `user_id`. It stays a platform feed. This table would store a copy of fields that already existed on a source row at the time the signed-in user opened it.

```text
decision_journal_entries
  id uuid primary key
  user_id uuid not null references public.users(id)
  source_kind text not null          -- live_signal or signal_history
  source_id text not null
  symbol text not null
  recorded_at timestamptz not null   -- timestamp from the source, not "now" as a substitute
  copied_fields jsonb not null       -- allowlisted source fields only
  created_at timestamptz not null default now()
```

- Unique index on `(user_id, source_kind, source_id)` so a repeat view does not duplicate the row.
- Index on `(user_id, recorded_at desc)` for that customer’s list.
- RLS enabled and forced. `authenticated` may `SELECT` only where `user_id = public.current_app_user_id()`. No `INSERT`, `UPDATE`, or `DELETE` for `authenticated`. The API writes with the service role after the same Signals subscription check used by the report.
- `copied_fields` may contain direction, lifecycle word, gate labels, and source timestamps. It must not contain broker passwords, tokens, account numbers, or a reconstructed risk limit.
- Retention proposal: delete rows whose `created_at` is older than 24 months. That job is not part of this proposal’s first migration. Until it is approved, rows would remain.
- Backfill: none. History rows have no owner.
- Rollback: revoke the API write, then `DROP TABLE public.decision_journal_entries`. Do not drop `signal` history or licenses.

## 7. Proposed migration: durable Growth job history

Not approved. The run, stop-release, draft, and publish routes stay unmounted. Creating this table must not start a job or release the emergency stop.

```text
growth_job_runs
  id uuid primary key
  idempotency_key text not null
  job_id text not null
  requested_by uuid not null references public.users(id)
  requested_at timestamptz not null
  finished_at timestamptz
  status text not null               -- succeeded, failed, stopped
  result jsonb not null default '{}'
```

- Unique index on `idempotency_key`.
- Index on `(requested_at desc)`.
- RLS enabled and forced. `authenticated` policies use `USING (false)`. Only the service role, behind the designated-owner check, may read or insert.
- A row is inserted only after a check finishes or fails. A stopped request can be stored as `stopped` with `result` empty. A row must not be marked `succeeded` when the check did not run.
- `result` may contain catalog price echoes, null metric declarations, and error codes. It must not contain tokens, refresh tokens, or customer trading payloads.
- The in-process log is wiped on restart. Do not copy it into this table.
- Retention proposal: delete rows older than 90 days.
- Rollback: drop `public.growth_job_runs` only.

Neither proposal changes billing prices, entitlements, trading logic, or the read-only Growth screen.
