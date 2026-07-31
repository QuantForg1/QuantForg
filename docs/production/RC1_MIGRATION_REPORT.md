# RC1 Migration Report

Generated: `2026-07-31T12:30:00Z`

## Policy

- Migrations were **NOT** applied by this run.
- Production apply is blocked until staging verification.

## Repository

- Supabase up migrations: `49`
- Alembic revisions: `['0001_baseline.py']`
- DSN present: `True` (via Railway service variables)
- DSN (redacted): `postgresql://***@db.otqyhlmwaifokrczryrc.supabase.co:5432/postgres`

## Remote

- Source: unavailable from agent egress
- Error: `OSError: Network is unreachable` to Supabase DB host
- Version count: unverified
- Tables sampled: unverified

## Pending (best-effort vs repo)

- Remote catalog unavailable — treat pending as **unverified**, not empty.

## Notes

- No staging Railway environment exists to apply migrations safely first.
- Production apply remains blocked.
