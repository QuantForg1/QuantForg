# QuantForg v1.0.0 — Final Production Review

Review date: 2026-07-22. No architecture redesign. No second AI.

| Domain | State contract | Contradictions checked |
| --- | --- | --- |
| Broker | Live `/weltrade/health` + `/mt5/status` | Must match Monitoring + Auto Trading gateway facts |
| Gateway | Connected only when probe succeeds | Offline ⇒ critical alert; no fake connected |
| Terminal | Sole live execution surface | No parallel ticket inventing fills |
| Monitoring | Ops + reliability probes | Incidents page wired to `/ite/reliability/incidents` |
| Auto Trading | Gates from live facts + status snapshot | Risk FAIL not invented; reason_groups honest |
| Risk | Peak equity HWM + daily PnL from MT5 deals | Approximations documented; fail closed when missing |
| Safety | Kill switch + execution safety locks | Armed ⇒ no new submissions |
| Execution | Validate → risk → safety → submit | Ambiguous transport non-retryable |
| Decision | Prefer No Trade | Advisory layers read-only |
| Research | Durable append-only archives | No overwrite of IVP/LLP/RMIP/PRC |
| Validation | Certification / Demo path | Live Real not auto-certified |
| Learning | ASI advisory | Sample history removed — live history only |
| Certification | Go/No-Go + checklist endpoints | Controlled live only until soak wall-clock done |

## Explicit remaining limitations

1. Multi-day soak (24h / 72h / 7d) requires dedicated host wall-clock — accelerated soak is CI-safe, not a substitute claim.  
2. Process-local DurableResearchStore needs export from the running API for full archive continuity.  
3. Candle history API ≤5000-bar window filter (medium).  
4. `EXECUTION_ENABLED` default false until operator Demo certification.

## Verdict

**RELEASE CANDIDATE v1.0.0 — READY FOR CONTROLLED LIVE DEPLOYMENT** after operator completes wall-clock soak targets and Demo certification. Not an unrestricted GA claim without soak completion evidence.  
