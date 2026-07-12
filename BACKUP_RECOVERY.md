# Backup & Recovery

**Release:** QuantForg v1.0.0-rc.1  

## What to back up

| Asset | Location | Notes |
|-------|----------|-------|
| Postgres / Supabase data | Managed DB or self-hosted volume | Primary durable store |
| Migration history | `supabase/migrations/` (in git) | Source of truth for schema |
| App config secrets | Secret manager / sealed `.env` | Not in git |
| Redis | Ephemeral cache | Rebuildable; optional RDB/AOF |
| Container images | Registry tags | Pin `quantforg:1.0.0-rc.1` |

Feature memory UoWs used in default DI are **not** durable — do not rely on process memory for recovery.

## Migration verify scripts

```bash
./scripts/verify_rollback_pairs.sh          # static: every up has a down
DATABASE_URL=postgresql://... ./scripts/verify_migrations.sh  # empty DB apply + rollback + re-apply
```

## Backup

### Database

1. Prefer provider snapshots (Supabase PITR / automated backups).  
2. Logical dump example:

```bash
pg_dump --format=custom --file=quantforg_$(date -u +%Y%m%dT%H%M%SZ).dump \
  "$DATABASE_URL"
```

3. Store dumps encrypted off-host; test restore quarterly.

### Application artifacts

- Tag and push Docker images for each RC.  
- Retain matching OpenAPI (`openapi/openapi.v1.0.0-rc1.json`) and this doc set.

## Restore

1. Provision empty Postgres; restore dump or PITR.  
2. Confirm migrations are at expected revision (re-apply ups only if schema empty).  
3. Deploy matching app image; inject secrets.  
4. Confirm `EXECUTION_ENABLED=false`.  
5. Probe `/api/v1/health/live` then `/api/v1/health/ready`.  
6. Smoke-test auth login and `/api/v1/version`.

## Rollback

| Layer | Action |
|-------|--------|
| App | Redeploy previous image tag; keep env compatible |
| Schema | Run `supabase/migrations/down/<migration>.down.sql` in reverse order for migrations unique to the failed release |
| Config | Revert secret/config change that caused the incident |
| Feature flags | Ensure `EXECUTION_ENABLED` remains false |

Never skip downs when rolling back schema that added tables with data you still need — export first.

## Disaster scenarios

| Scenario | Response |
|----------|----------|
| Region / DB loss | Restore latest good backup to new region; update DNS/connection strings |
| Bad migration | Stop traffic; down-migrate; redeploy previous app |
| Secret leak | Rotate `SECRET_KEY`, encryption keys, Supabase keys, DB password; invalidate sessions |
| Accidental execution enable | Immediately set `EXECUTION_ENABLED=false`, restart, audit `/ops/audit` + execution decisions |

## Incident response

1. **Detect** — health 503, alerts (`/ops/alerts`), error-rate spike on `/metrics`.  
2. **Contain** — drain traffic; disable risky flags (`EXECUTION_ENABLED=false`).  
3. **Diagnose** — logs by request ID; Audit Center categories.  
4. **Eradicate** — patch/rollback; rotate secrets if needed.  
5. **Recover** — restore/backup path; verify probes green.  
6. **Review** — postmortem; update runbooks in `OPERATIONS.md`.

## RTO / RPO (targets for RC1 staging)

| Metric | Staging target |
|--------|----------------|
| RTO | < 4 hours (manual restore) |
| RPO | Last successful backup (daily recommended) |

Production GA should tighten these with automated PITR and rehearsed drills.
