# QuantForg v1.0.0 — Recovery Guide

## Principles

- Fail closed. Prefer No Trade.  
- Never auto-retry ambiguous `order_send`.  
- Restore peak equity / risk state before re-enabling Auto Trading.  
- Matching app image tag + schema revision.

## State to restore

| Asset | Source |
| --- | --- |
| Postgres | Supabase PITR / `pg_dump` restore |
| Peak equity / daily PnL | `.quantforg_state/live_account_risk.json` + DB table |
| Research / IVP / LLP / RMIP / PRC | Durable store export / backup script snapshot |
| Audit logs | Postgres `execution_audits` (+ ops audit) |
| Secrets | Rotate if leak suspected |

```bash
python scripts/backup_production_state.py --out backups/manual_restore_point
```

## Gateway reconnect

1. Arm kill switch.  
2. Pause Auto Trading.  
3. Restart Windows gateway service.  
4. Verify gateway `/health` and API probes.  
5. Confirm Monitoring ≡ Broker.  
6. Disarm only when green.

## Broker failure

1. Arm kill; Auto Trading OFF.  
2. Capture last retcodes / request ids.  
3. Wait for broker confirmation — do not invent fills.  
4. Re-login MT5 after broker sessions healthy.  
5. Reconcile positions vs terminal.

## Disaster recovery

1. Declare incident; kill armed.  
2. Restore Postgres to latest verified backup.  
3. Restore `.quantforg_state` peak equity.  
4. Redeploy matching `1.0.0` image.  
5. `EXECUTION_ENABLED=false` until smoke + launch locks PASS (Demo Certification optional).  
6. Run `startup` + `recovery` runbooks.

## Emergency stop

`POST /ite/ops/auto-trading/emergency-stop` and/or arm kill switch. Flatten only via PME/OMS when safe — never invent closes.

## Post-recovery verify

- `/health/live` + `/ready`  
- `/ite/ops/services-health`  
- Peak equity loaded  
- No contradictory desk states (see [Production Review](./PRODUCTION_REVIEW.md))  
