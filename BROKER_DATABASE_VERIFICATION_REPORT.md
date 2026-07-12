# BROKER_DATABASE_VERIFICATION_REPORT

**Status:** PASSED  
**Date:** 2026-07-12  
**Project:** `otqyhlmwaifokrczryrc`  
**Apply method:** `supabase db push` (session pooler `aws-0-eu-central-1`)

## Migrations

| Version | Remote |
|--------:|:------:|
| `20260712120000` | applied |
| `20260712120100` | applied |
| `20260712120200` | applied |
| `20260712130000` | applied |
| `20260712130100` | applied |
| `20260712130200` | applied |
| `20260712140000` | applied |
| `20260712140100` | applied |
| `20260712141000` | applied |
| `20260712141100` | applied |

**Pending migrations:** none

Newly applied in this finalize run:

- `20260712140000_broker_foundation.sql`
- `20260712140100_broker_foundation_rls.sql`
- `20260712141000_broker_sessions.sql`
- `20260712141100_broker_sessions_rls.sql`

## Broker tables

| Table | RLS enabled | RLS forced |
|-------|:-----------:|:----------:|
| `brokers` | yes | yes |
| `broker_capabilities` | yes | yes |
| `broker_accounts` | yes | yes |
| `broker_credentials` | yes | yes |
| `broker_connections` | yes | yes |
| `broker_sessions` | yes | yes |

Catalogue extensions confirmed:

- `brokers.platform_code`
- `brokers.description`
- `broker_credentials.status`

## Counts

| Object | Count |
|--------|------:|
| RLS policies (broker tables) | 18 |
| Indexes | 24 |
| Triggers (`set_updated_at`) | 6 |
| Constraints | 83 |
| Foreign keys | 7 |

## Foreign keys (summary)

- `broker_capabilities.broker_id` → `brokers.id`
- `broker_accounts.user_id` → `users.id`
- `broker_accounts.broker_id` → `brokers.id`
- `broker_credentials.broker_account_id` → `broker_accounts.id`
- `broker_connections.broker_account_id` → `broker_accounts.id`
- `broker_sessions.broker_account_id` → `broker_accounts.id`
- `broker_sessions.connection_id` → `broker_connections.id`

## Notes

- Credential payloads remain ciphertext columns (`encrypted_payload`); no plaintext secrets in schema.
- `broker_sessions` has a partial unique index for one active (`connected`) session per account.
- Down scripts exist under `supabase/migrations/down/` for all four broker migrations.
