# RC1 — Deployment

See also [Deployment](../deployment.md).

## Surfaces

| Surface | Host |
| --- | --- |
| Frontend | Vercel / static Next.js |
| API | Railway |
| Database | Supabase Postgres |
| Gateway | Windows + Cloudflare Tunnel |

## Migrations

Supabase SQL migrations under `supabase/migrations/`.

RC1-critical:

- `20260720190000_execution_audits.sql`
- `20260720190100_execution_audits_rls.sql`
- `20260720200000_rc1_revoke_anon_security_definer.sql`

Rollback scripts: `supabase/migrations/down/`.

## Environment (production)

- `APP_ENV=production`, `DEBUG=false`
- Strong `SECRET_KEY`, DB URL, Supabase keys (service role server-only)
- `MT5_GATEWAY_BASE_URL` + gateway token
- Restricted `CORS_ORIGINS` / `ALLOWED_HOSTS`
- `RAILWAY_PUBLIC_DOMAIN` for Railway self-probe

## Release rule

Ship only when quality gate is green: lint · typecheck · build · tests.
