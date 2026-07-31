# RC1 Migration Audit (Infra Recovery)

Generated: `2026-07-31T12:40:45.026742Z`

## Policy

- Migrations were **NOT** applied.
- Production apply remains blocked.
- No automatic migrations.

## Connectivity

- DSN present: `True`
- DSN (redacted): `postgresql://***@aws-0-eu-central-1.pooler.supabase.com:5432/postgres`
- Remote source: `supabase_migrations.schema_migrations via DATABASE_URL`
- Remote version count: `49`
- Public/supabase tables: `84`

## Repo

- Supabase up migrations: `49`
- Alembic: `['0001_baseline.py']`

## Pending vs remote (repo not on remote)

- None

## Extra on remote (not in repo filenames)

- None

## Notes

- all repo supabase migration versions appear present on remote
- migrations NOT applied by this audit
