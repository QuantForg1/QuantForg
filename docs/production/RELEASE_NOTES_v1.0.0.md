# QuantForg v1.0.0 — Release Notes

## Summary

Institutional production-readiness pack for long-running operation: services health, production alerts, soak/backup harnesses, operator runbooks, dashboard cleanup (no fabricated ASI samples), and documentation for Architecture / Operations / Deployment / Recovery.

**No new product modules. No architecture redesign. No second AI.**

## Added

- `GET /ite/ops/services-health` — per-service status, latency, last error, live alerts  
- Production alert kinds + `evaluate_production_alerts` (deduped unacked alerts)  
- Expanded ops runbooks: startup, shutdown, restart, broker_failure, recovery, disaster_recovery, incident_response  
- `scripts/institutional_soak.py` — accelerated + optional wall-clock stability reports  
- `scripts/backup_production_state.py` — peak equity / state artifact backup  
- `scripts/config_audit.py` — Settings unused/conflict audit  
- `docs/production/*` guides + checklist + review  

## Changed

- Incidents desk loads live `/ite/reliability/incidents`  
- ASI workspace evaluates with live history only (sample history removed)  
- Ops alert raise is deduped by kind while unacked  

## Migration notes

1. Apply pending Supabase migrations (peak equity / live account risk if not yet applied).  
2. Ensure `.quantforg_state/` is on durable volume for API hosts.  
3. Schedule `backup_production_state.py` + Postgres backups.  
4. Point operators at `docs/production/OPERATIONS_GUIDE.md`.  
5. Run soak wall-clock on a dedicated host before unrestricted live volume.

## Known limitations

- Wall-clock 24h / 72h / 7d soak not completed in this packaging session — harness + accelerated profiles only.  
- DurableResearchStore is process-local unless exported.  
- Default `EXECUTION_ENABLED=false`.  
- Candle API bar-window filter (medium) remains.

## Production checklist

See `docs/production/PRODUCTION_CHECKLIST.md`.  
