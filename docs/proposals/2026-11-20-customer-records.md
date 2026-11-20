# Customer record proposals — not applied

These tables are not created. Do not run this plan against production until the owner approves this exact document. No historical backfill is possible from data that was never stored.

## Referral ledger

Ownership: `referrer_user_id` owns the code. `referred_user_id` owns the registration. A reward row, when a later approved schedule exists, belongs to the referrer.

Tables:

- `referral_codes`: `user_id` primary key, `code` unique, `created_at`.
- `referral_attributions`: `referred_user_id` primary key, `referrer_user_id`, `code`, `created_at`. One attribution per referred account.
- `referral_events`: `id`, `referred_user_id`, `event_type`, `source_id` unique, `created_at`.
- `referral_rewards`: `id`, `event_id` unique, `status`, `amount` null, `currency` null.

RLS: authenticated users can select their own code and attributions where they are the referrer or the referred user. Inserts and updates are service-role only. No policy grants one customer another customer's rows.

Indexes: unique `referral_codes.code`, unique `referral_attributions.referred_user_id`, unique `referral_events.source_id`.

Retention: keep attribution for the life of both accounts. Do not delete it during an account export.

Impact: empty tables. Existing billing and users are unchanged.

Backfill: not possible. Past registrations have no stored referral code.

Rollback: drop the four tables. No existing column changes.

Security tests before any apply: self-referral rejected, second attribution rejected, customer A cannot select customer B, reward amount stays null.

The current code records eligibility only. It does not pay anyone.

## Community

Tables:

- `community_profiles`: `user_id` primary key, `visibility` default `private`, `updated_at`.
- `community_posts`: `id`, `author_id`, `body`, `created_at`.
- `community_comments`: `id`, `post_id`, `author_id`, `body`, `created_at`.
- `community_reports`: `id`, `reporter_id`, `subject_type`, `subject_id`, `created_at`.
- `community_blocks`: `blocker_id`, `blocked_id`, primary key on both.

RLS: a user selects and updates only their profile. A user inserts posts and comments only as themselves. A user updates or deletes only rows whose `author_id` is themselves. Reports are insert-own and not readable by other customers. Blocks are select-own. Moderator access is a separate server role, not a browser check.

Indexes: `community_posts (created_at desc)`, `community_comments (post_id, created_at)`.

Retention: reports kept for moderation review. Deleting an account must not leave another customer's private text readable.

Impact: no existing posts, so there is nothing to import.

Backfill: not possible. There is no community history.

Rollback: drop the five tables.

Security tests: customer B cannot edit customer A's post; a private profile is not readable by another customer; a block hides the profile; page size is capped.

## Decision journal and growth job history

`phase_a_decision_journal_enabled` already exists and defaults off. A durable decision journal and durable growth job history still need their own reviewed migration. This document does not authorize those tables. Growth job routes stay unmounted. Opening a page is not a viewed-report count.

## Search Console and GA4

No Google token is stored in the repository. Status is `not_connected` until the owner creates an OAuth client, enables the Search Console API and the Google Analytics Data API, and places the client id, client secret, refresh token, site URL, and GA4 property id in the production secret store. Even then, impressions, subscribers, revenue, churn, and activation stay null until a sync has been run and checked. Do not paste those secrets into chat.
