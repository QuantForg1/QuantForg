# Railway Staging Operator Steps (RC1)

Agent token can `railway status` / `railway run -s QuantForg` against **production** only.

Observed contradiction (evidence in `railway_staging_blocked.json`):

- `railway environment create staging` → “An environment with that name already exists”
- `railway environment list --json` → only `production`
- `https://quantforg-staging.up.railway.app/health` → Application not found
- GraphQL project query → Not Authorized with current project token

## Required human actions (Railway dashboard)

1. Open project **QuantForg** (`76f9026d-362f-4e16-961d-44e7a090459a`).
2. Locate or purge the hidden/orphan **staging** environment name collision.
3. Ensure a real **staging** environment is visible and linkable.
4. Create/clone a QuantForg service under staging (do **not** point staging traffic at production accidentally).
5. Deploy branch with RC1 validation routes (e.g. `cursor/infra-recovery-rc1-bc83` or stacked RC1 PR tip).
6. Verify:
   - `GET https://<staging-host>/health` → 200
   - Authenticated `GET /api/v1/ite/ops/rc1-production-validation` → 200
7. **Do not** merge to main or auto-deploy production as part of this recovery.

## Policy

- No production deploy from this mission.
- No automatic DB migrations.
