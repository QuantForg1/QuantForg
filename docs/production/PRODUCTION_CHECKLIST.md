# QuantForg v1.0.0 — Production Checklist

## Pre-deploy

- [ ] Secrets rotated; no default `SECRET_KEY` in production  
- [ ] `EXECUTION_ENABLED=false` until Demo cert  
- [ ] Gateway URL + caller token configured  
- [ ] Migrations applied (incl. live account risk)  
- [ ] `python scripts/config_audit.py` reviewed  
- [ ] Backup taken (`backup_production_state.py` + `pg_dump`)

## Post-deploy smoke

- [ ] `/api/v1/health/live` 200  
- [ ] `/api/v1/health/ready` expected status  
- [ ] `/ite/ops/services-health` reachable (OWNER)  
- [ ] Monitoring ≡ Broker gateway state  
- [ ] Kill switch state intentional  
- [ ] Auto Trading OFF / SHADOW  

## Stability

- [ ] Accelerated soak `stress` green  
- [ ] Wall sample (≥30s) captured  
- [ ] 24h wall soak scheduled / complete (dedicated host)  
- [ ] 72h wall soak scheduled / complete  
- [ ] 7d wall soak scheduled / complete  

## Alerts

- [ ] Gateway disconnect raises alert  
- [ ] Alert ack path works  
- [ ] Disk / memory thresholds understood  

## Go-live

- [ ] Demo certification trade complete  
- [ ] Canary period stable  
- [ ] OWNER sign-off recorded  
- [ ] Runbooks exercised once in staging  
- [ ] `GET /ite/ops/launch-readiness` — all required items PASS  
- [ ] Railway `EXECUTION_ENABLED=true` (env only; no API flip)  
- [ ] OWNER promote: `POST /ite/ops/launch-readiness/promote` with `confirmed=true`  
  — or CLI: `poetry run python scripts/launch_readiness.py --remote --promote --confirm`  
- [ ] Verify: Ops LIVE · Gate Enabled · Execution ON · Auto Trading RUNNING  

## Quality gate

- [ ] ruff  
- [ ] pytest  
- [ ] integration (CI)  
- [ ] frontend lint  
- [ ] frontend typecheck  
- [ ] frontend build  
