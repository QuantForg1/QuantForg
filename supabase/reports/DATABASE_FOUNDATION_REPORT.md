# QuantForg Supabase Database Foundation Report

**Status:** Migrations authored — **not applied**. Awaiting confirmation before any remote/local apply.

**Date:** 2026-07-12  
**Project id (config):** `otqyhlmwaifokrczryrc`  
**Source of truth:** `app/domain/entities/*`  
**Scope:** Supabase SQL migrations only (no business logic / UI changes)

---

## 1. Migrations

| Version | File | Purpose |
|--------:|------|---------|
| 20260712120000 | `supabase/migrations/20260712120000_extensions_helpers.sql` | `pgcrypto`, `set_updated_at()`, `forbid_mutation()` |
| 20260712120100 | `supabase/migrations/20260712120100_domain_tables.sql` | 13 domain tables, PKs/FKs/indexes/checks/timestamps/triggers |
| 20260712120200 | `supabase/migrations/20260712120200_rls_policies.sql` | RLS enable/force + policies + `current_app_user_id()` |

### Reversibility (down scripts)

| Up | Down |
|----|------|
| `...20000_extensions_helpers.sql` | `migrations/down/20260712120000_extensions_helpers.down.sql` |
| `...20100_domain_tables.sql` | `migrations/down/20260712120100_domain_tables.down.sql` |
| `...20200_rls_policies.sql` | `migrations/down/20260712120200_rls_policies.down.sql` |

Down order (apply reverse of up): RLS → tables → helpers.

`pgcrypto` is **not** dropped on reverse (shared extension safety).

### Seed (development only)

- `supabase/seed.sql` — wired in `config.toml` `[db.seed]`
- Loaded by local `supabase db reset` only
- **Do not** apply to production

---

## 2. Tables created (13)

| Table | Role | Mutable |
|-------|------|---------|
| `users` | Platform identity | yes |
| `brokers` | Broker catalogue | yes |
| `licenses` | Entitlements | yes |
| `symbols` | Instrument catalogue | yes |
| `trading_accounts` | User↔broker account | yes |
| `trading_sessions` | Connection window | yes |
| `strategy_metadata` | Strategy catalogue | yes |
| `risk_profiles` | Declared risk limits | yes |
| `orders` | Order intent | yes |
| `positions` | Open exposure | yes |
| `trades` | Fill ledger | **append-only** |
| `signals` | Direction suggestions | yes |
| `audit_logs` | Forensic log | **append-only** |

All tables: UUID PK (`gen_random_uuid()`), `created_at` / `updated_at` (`timestamptz`, UTC).

Optional: `users.auth_user_id` → `auth.users(id)` when Auth schema exists.

---

## 3. Indexes (42)

**Unique**

- `users_email_uidx` — `lower(email)`
- `brokers_slug_uidx` — `lower(slug)`
- `symbols_code_broker_uidx` — `(lower(code), coalesce(broker_id, …))`
- `trading_accounts_broker_account_uidx` — `(broker_id, lower(account_number))`
- `strategy_metadata_slug_version_uidx` — `(lower(slug), lower(version))`
- `risk_profiles_one_active_per_user_account_uidx` — one active profile per user/account

**Lookup / FK support**

- users: `status`, `auth_user_id` (partial)
- brokers: `status`
- licenses: `user_id`, `status`
- symbols: `status`, `broker_id` (partial)
- trading_accounts: `user_id`, `status`
- trading_sessions: `trading_account_id`, `user_id`, `status`
- strategy_metadata: `owner_user_id`, `status`
- risk_profiles: `user_id`, `trading_account_id` (partial)
- orders: `trading_account_id`, `symbol_id`, `status`, `submitted_at DESC`
- positions: `trading_account_id`, `symbol_id`, `status`, `opening_order_id` (partial)
- trades: `trading_account_id`, `symbol_id`, `executed_at DESC`, `order_id` / `position_id` (partial)
- signals: `symbol_id`, `status`, `trading_account_id` / `strategy_metadata_id` (partial)
- audit_logs: `actor_user_id` (partial), `(resource_type, resource_id)`, `occurred_at DESC`

Plus primary keys and unique constraints on `users.auth_user_id`.

---

## 4. Triggers (15)

| Trigger | Table | Function |
|---------|-------|----------|
| `*_set_updated_at` ×11 | all mutable tables | `set_updated_at()` |
| `trades_forbid_update` / `trades_forbid_delete` | `trades` | `forbid_mutation()` |
| `audit_logs_forbid_update` / `audit_logs_forbid_delete` | `audit_logs` | `forbid_mutation()` |

Mutable tables with `updated_at` triggers: users, brokers, licenses, symbols, trading_accounts, trading_sessions, strategy_metadata, risk_profiles, orders, positions, signals.

---

## 5. RLS policies (35)

RLS **enabled + forced** on all 13 tables.

Helper: `public.current_app_user_id()` — maps `auth.uid()` → `users.id` (`SECURITY DEFINER`, execute granted to `authenticated` / `service_role`).

| Table | Policies |
|-------|----------|
| `users` | select/update/insert own (`auth_user_id` / app id) |
| `brokers` | select authenticated (catalogue) |
| `symbols` | select authenticated (catalogue) |
| `licenses` | select/insert/update own |
| `trading_accounts` | select/insert/update own |
| `trading_sessions` | select/insert/update own |
| `strategy_metadata` | select/insert/update/delete own |
| `risk_profiles` | select/insert/update/delete own |
| `orders` | select/insert/update via owned account |
| `positions` | select/insert/update via owned account |
| `trades` | select/insert via owned account (no update/delete policy) |
| `signals` | select/insert/update via account or owned strategy |
| `audit_logs` | select own actor; insert with actor null or self |

Writes to catalogue tables (`brokers`, `symbols`) intentionally have **no** authenticated write policies — use `service_role` / backend.

---

## 6. Verification performed

| Check | Result |
|-------|--------|
| Domain entities ↔ tables | Aligned (13 aggregates) |
| FK create order | Children after parents |
| Destructive SQL scan (`DROP DATABASE`, `TRUNCATE`, `DROP SCHEMA public`) | None in up migrations |
| Down scripts present for each up | Yes |
| Empty-DB apply (Docker / Supabase CLI) | **Not run** — `supabase` CLI and Docker unavailable in this environment |

### Recommended apply path (after your confirmation)

```bash
# Local empty DB (preferred first)
supabase db reset

# Or push to linked remote project
supabase db push
```

---

## 7. Confirmation gate

**Stopped before applying migrations.**

Please confirm one of:

1. **Local only** — `supabase db reset` (migrations + seed)
2. **Remote linked project** — `supabase db push` (migrations only; no seed)
3. **Hold** — leave unapplied

No secrets were written into migration or seed files.
