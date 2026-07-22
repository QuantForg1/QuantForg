# QuantForg v1.0.0 — Migration Notes

## Schema

Apply migrations in order under `supabase/migrations/`. Critical for risk HWM:

- `20260722180000_live_account_risk_state.sql` (if present in tree)

Downs live under `supabase/migrations/down/`.

## Application state

| Path | Action |
| --- | --- |
| `.quantforg_state/live_account_risk.json` | Persist across deploys (volume) |
| Process DurableResearchStore | Export via backup script / API before recycle |

## Configuration

| Change | Action |
| --- | --- |
| `BETA_INVITE_CODE` | Server-only; remove any `NEXT_PUBLIC_BETA_INVITE_CODE` |
| `MT5_GATEWAY_ALLOW_QUERY_TOKEN` | Default false — use headers |
| `EXECUTION_ENABLED` | Remain false until OWNER launch locks PASS (Demo cert optional) |

Run `python scripts/config_audit.py` and review unused / conflicts.

## Operator cutover

1. Deploy API + frontend `1.0.0`.  
2. Verify services-health.  
3. Train on new runbooks (`startup`, `emergency_shutdown`, `disaster_recovery`).  
4. Schedule soak wall-clock jobs.  
