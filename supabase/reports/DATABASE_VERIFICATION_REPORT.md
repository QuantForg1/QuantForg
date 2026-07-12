# QuantForg DATABASE_VERIFICATION_REPORT

**Status:** PASSED — remote migrations applied and verified
**Date:** 2026-07-12
**Project ref:** `otqyhlmwaifokrczryrc`
**Apply method:** `supabase db push --db-url` (Session pooler, `aws-0-eu-central-1`)
**Seed data:** Not applied

---

## 1. Auth / link notes

- Supabase CLI login with the provided personal access token **failed**: token format was invalid for Supabase CLI (expected `sbp_…`).
- Direct host `db.<ref>.supabase.co:5432` was unreachable from this environment (IPv6-only / timeout).
- Migrations were applied successfully using the project database password over the Supabase connection pooler.
- `supabase/config.toml` uses `project_id = "otqyhlmwaifokrczryrc"`.
- Formal `supabase link` was not completed without a valid Supabase access token; schema apply/verify did not require it.

---

## 2. Migrations

| Local | Remote | Status |
|------:|-------:|--------|
| 20260712120000 | 20260712120000 | applied |
| 20260712120100 | 20260712120100 | applied |
| 20260712120200 | 20260712120200 | applied |

**Pending migrations:** none (`supabase migration list` shows local == remote for all three).

Applied files:

1. `20260712120000_extensions_helpers.sql`
2. `20260712120100_domain_tables.sql`
3. `20260712120200_rls_policies.sql`

---

## 3. Tables (13/13)

- `users`
- `brokers`
- `licenses`
- `symbols`
- `trading_accounts`
- `trading_sessions`
- `strategy_metadata`
- `risk_profiles`
- `orders`
- `positions`
- `trades`
- `signals`
- `audit_logs`

All expected domain tables present: **True**

---

## 4. Row Level Security

- All domain tables RLS enabled: **True**
- All domain tables RLS forced: **True**

| Table | RLS enabled | RLS forced |
|-------|:-----------:|:----------:|
| `audit_logs` | True | True |
| `brokers` | True | True |
| `licenses` | True | True |
| `orders` | True | True |
| `positions` | True | True |
| `risk_profiles` | True | True |
| `signals` | True | True |
| `strategy_metadata` | True | True |
| `symbols` | True | True |
| `trades` | True | True |
| `trading_accounts` | True | True |
| `trading_sessions` | True | True |
| `users` | True | True |

### Policies (35)

**users** (3)
- `users_insert_own (INSERT)`
- `users_select_own (SELECT)`
- `users_update_own (UPDATE)`

**brokers** (1)
- `brokers_select_authenticated (SELECT)`

**licenses** (3)
- `licenses_insert_own (INSERT)`
- `licenses_select_own (SELECT)`
- `licenses_update_own (UPDATE)`

**symbols** (1)
- `symbols_select_authenticated (SELECT)`

**trading_accounts** (3)
- `trading_accounts_insert_own (INSERT)`
- `trading_accounts_select_own (SELECT)`
- `trading_accounts_update_own (UPDATE)`

**trading_sessions** (3)
- `trading_sessions_insert_own (INSERT)`
- `trading_sessions_select_own (SELECT)`
- `trading_sessions_update_own (UPDATE)`

**strategy_metadata** (4)
- `strategy_metadata_delete_own (DELETE)`
- `strategy_metadata_insert_own (INSERT)`
- `strategy_metadata_select_own (SELECT)`
- `strategy_metadata_update_own (UPDATE)`

**risk_profiles** (4)
- `risk_profiles_delete_own (DELETE)`
- `risk_profiles_insert_own (INSERT)`
- `risk_profiles_select_own (SELECT)`
- `risk_profiles_update_own (UPDATE)`

**orders** (3)
- `orders_insert_own (INSERT)`
- `orders_select_own (SELECT)`
- `orders_update_own (UPDATE)`

**positions** (3)
- `positions_insert_own (INSERT)`
- `positions_select_own (SELECT)`
- `positions_update_own (UPDATE)`

**trades** (2)
- `trades_insert_own (INSERT)`
- `trades_select_own (SELECT)`

**signals** (3)
- `signals_insert_own (INSERT)`
- `signals_select_own (SELECT)`
- `signals_update_own (UPDATE)`

**audit_logs** (2)
- `audit_logs_insert_authenticated (INSERT)`
- `audit_logs_select_own (SELECT)`

---

## 5. Indexes (56 including primary keys)

**users** (5)
- `users_auth_user_id_idx`
- `users_auth_user_id_key`
- `users_email_uidx`
- `users_pkey`
- `users_status_idx`

**brokers** (3)
- `brokers_pkey`
- `brokers_slug_uidx`
- `brokers_status_idx`

**licenses** (3)
- `licenses_pkey`
- `licenses_status_idx`
- `licenses_user_id_idx`

**symbols** (4)
- `symbols_broker_id_idx`
- `symbols_code_broker_uidx`
- `symbols_pkey`
- `symbols_status_idx`

**trading_accounts** (4)
- `trading_accounts_broker_account_uidx`
- `trading_accounts_pkey`
- `trading_accounts_status_idx`
- `trading_accounts_user_id_idx`

**trading_sessions** (4)
- `trading_sessions_account_idx`
- `trading_sessions_pkey`
- `trading_sessions_status_idx`
- `trading_sessions_user_id_idx`

**strategy_metadata** (4)
- `strategy_metadata_owner_idx`
- `strategy_metadata_pkey`
- `strategy_metadata_slug_version_uidx`
- `strategy_metadata_status_idx`

**risk_profiles** (4)
- `risk_profiles_account_idx`
- `risk_profiles_one_active_per_user_account_uidx`
- `risk_profiles_pkey`
- `risk_profiles_user_id_idx`

**orders** (5)
- `orders_account_idx`
- `orders_pkey`
- `orders_status_idx`
- `orders_submitted_at_idx`
- `orders_symbol_idx`

**positions** (5)
- `positions_account_idx`
- `positions_opening_order_idx`
- `positions_pkey`
- `positions_status_idx`
- `positions_symbol_idx`

**trades** (6)
- `trades_account_idx`
- `trades_executed_at_idx`
- `trades_order_idx`
- `trades_pkey`
- `trades_position_idx`
- `trades_symbol_idx`

**signals** (5)
- `signals_account_idx`
- `signals_pkey`
- `signals_status_idx`
- `signals_strategy_idx`
- `signals_symbol_idx`

**audit_logs** (4)
- `audit_logs_actor_idx`
- `audit_logs_occurred_at_idx`
- `audit_logs_pkey`
- `audit_logs_resource_idx`

---

## 6. Triggers (15 unique / 15 event rows)

**users**
- `users_set_updated_at [BEFORE UPDATE]`

**brokers**
- `brokers_set_updated_at [BEFORE UPDATE]`

**licenses**
- `licenses_set_updated_at [BEFORE UPDATE]`

**symbols**
- `symbols_set_updated_at [BEFORE UPDATE]`

**trading_accounts**
- `trading_accounts_set_updated_at [BEFORE UPDATE]`

**trading_sessions**
- `trading_sessions_set_updated_at [BEFORE UPDATE]`

**strategy_metadata**
- `strategy_metadata_set_updated_at [BEFORE UPDATE]`

**risk_profiles**
- `risk_profiles_set_updated_at [BEFORE UPDATE]`

**orders**
- `orders_set_updated_at [BEFORE UPDATE]`

**positions**
- `positions_set_updated_at [BEFORE UPDATE]`

**trades**
- `trades_forbid_delete [BEFORE DELETE]`
- `trades_forbid_update [BEFORE UPDATE]`

**signals**
- `signals_set_updated_at [BEFORE UPDATE]`

**audit_logs**
- `audit_logs_forbid_delete [BEFORE DELETE]`
- `audit_logs_forbid_update [BEFORE UPDATE]`

### Helper functions

- `public.current_app_user_id()`
- `public.forbid_mutation()`
- `public.set_updated_at()`

---

## 7. Verdict

| Check | Result |
|-------|--------|
| Migrations applied | PASS (3/3) |
| Pending migrations | PASS (none) |
| Tables created | PASS (13/13) |
| RLS enabled + forced | PASS |
| RLS policies | PASS (35) |
| Indexes | PASS (56) |
| Triggers | PASS (15) |
| Seed data | SKIPPED (as requested) |

No secrets are stored in this report.
