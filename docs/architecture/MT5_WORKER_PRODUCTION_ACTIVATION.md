# MT5 Worker Control Plane — Production Activation (Phase 1E)

## PR stack

| PR | Role | Base |
| --- | --- | --- |
| #207 | Account registry | `main` |
| #208 | Worker infra | #207 |
| #209 | Local Windows agent | #208 |
| #210 | Railway HTTP APIs | #209 |
| this | Postgres durable + sealed credentials | #210 |

## Migration approval required (do not apply silently)

**File:** `supabase/migrations/20261109160000_mt5_worker_control_plane_durable.sql`

Creates `public.mt5_worker_control_plane` with:
- RLS FORCE + deny `authenticated`
- `service_role` only grants
- Unique active indexes: host+slot, user_id, broker_account_id
- **No password columns**

Also depends on earlier Phase 1a/1B migrations already in the stack:
- `20261109120000_multi_account_foundation.sql`
- `20261109120100_multi_account_foundation_rls.sql`
- `20261109140000_mt5_worker_runtime.sql`

### Before Production apply

1. Confirm backup / PITR on Supabase project.  
2. Review SQL + down migration.  
3. Confirm RLS deny policies.  
4. Obtain **explicit owner approval** naming this migration.  
5. Apply via approved migration path (not ad-hoc).  

**Status:** Pending owner approval — not applied by this agent.

## Railway

1. Merge stack to `main` only after required checks are green.  
2. Confirm deploy commit SHA on Railway.  
3. Set `WORKER_SERVICE_TOKEN` in Railway variables (never commit/print).  
4. Optionally set lab-only `QF_DEMO_*` on Railway **only** for sealed-envelope lab tests — prefer real vault later.  
5. Verify:
   - `GET /api/v1/health/live`
   - `POST /api/v1/mt5-workers/register` with Bearer token
   - Heartbeat + revoke + sealed claim

## Sealed credentials

- `POST /credentials/claim` returns opaque `sealed_envelope`  
- No `password` field in JSON  
- Windows agent unwraps with `WORKER_SERVICE_TOKEN` + `worker_id`  
- Revoked workers denied  
- Without vault/`QF_DEMO_*`: `credential_material_unavailable` (honest, not invented success)

## LIVE safety

`MULTI_ACCOUNT_DISPATCH_ENABLED=false`  
`MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false`  
Weltrade singleton untouched.
