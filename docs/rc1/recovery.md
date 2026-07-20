# RC1 — Recovery

## Principles

1. Prefer read-only diagnosis before mutating state.
2. Never invent fills or audit rows.
3. Kill-switch / mode controls live under ITE ops (admin) — use confirmed actions only.

## Gateway / MT5 outage

1. Confirm Railway `/health`.
2. Probe gateway `/health` from Railway host.
3. Confirm Cloudflare tunnel is up.
4. Confirm MT5 terminal session on Windows host.
5. Resume only when probes show gateway + MT5 up.

## Database

1. Check Supabase status / advisors.
2. Confirm `execution_audits` RLS still forced.
3. Apply missing migrations; use `down/` only with explicit rollback plan.

## Audit chain gaps

If a request lacks expected stages:

- Check application logs for `execution_audit_failed` (non-blocking record path).
- Confirm unique index prevented duplicates (expected).
- Do not backfill fake stages.

## Rollback migration example

```sql
-- Only with approved change window
-- see supabase/migrations/down/20260720190100_execution_audits_rls.down.sql
-- see supabase/migrations/down/20260720190000_execution_audits.down.sql
```
