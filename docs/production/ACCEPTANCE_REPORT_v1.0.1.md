# QuantForg v1.0.1 — Acceptance Report

**Date:** 2026-07-22  
**Baseline:** QuantForg v1.0.1 (`140fbf5` optimization pack + this acceptance pack)  
**Scope:** Prove correct behavior under realistic scenarios. No new features. No architecture redesign. No trading-logic changes.

---

## Verdict

### **Accepted with Conditions**

### Recommendation

**ACCEPT WITH CONDITIONS**

Never unrestricted production solely from these tests.

---

## Evidence summary

| Area | Result | Notes |
| --- | --- | --- |
| 1. Trading scenario validation | **PASS** (simulated) | `tests/unit/test_acceptance_validation_v101.py` — London/NY/Tokyo, high spread, news blackout, market closed, MT5 down, broker timeout-style disconnect, duplicate signal, emergency stop |
| 2. Failure injection | **PASS** (in-process) | Phase H `FailureInjector` suite + chaos MT5/gateway + production alerts (latency/DB/calendar/disk/no-ticks) + recovery forbids `order_send` retry |
| 3. Consistency | **PASS** (unit) | Auto Trading facts ≡ ops health from shared `ProbeInputs` |
| 4. Audit trail | **PASS** (contract) | `ExecutionAuditStage` spine + `CERTIFICATION_PIPELINE` decision→…→journal; fill via MT5/journal evidence (no invented fill stage) |
| 5. Recovery | **PASS** (unit) | Peak equity reload; kill switch; duplicate identity import; safe-read recovery |
| 6. Long-running soak | **PENDING OPERATIONAL EVIDENCE** | Accelerated `stress` soak PASS; wall-clock 24h / 72h / 7d **not** claimed |

Artifacts:

- `docs/production/reports/soak_stress_*.json`
- `docs/production/reports/acceptance_evidence_*.json`
- Runner: `scripts/acceptance_validation.py`

Quality gates this session: acceptance/related unit pytest **48 passed**; soak stress **ok**; frontend typecheck/lint **ok**. Full CI integration suite remains an operational/CI prerequisite.

---

## Scenario expectations verified

| Scenario | Expected | Observed |
| --- | --- | --- |
| Normal London trend | Gates can allow when all facts green | `allowed=True` |
| New York session | Allowed when in policy | `allowed=True` |
| Asia / Tokyo | Allowed if session permitted; off-hours block | Pass |
| High spread | Prefer No Trade | Blocked |
| News blackout | Prefer No Trade | Blocked |
| Market closed / no ticks | Prefer No Trade | Blocked |
| MT5 reconnect while down | Block until connected | Block then allow |
| Broker timeout / gateway down | Block; alert path exists | Block + chaos degrade |
| Duplicate signal | No double claim | DuplicateProtection blocks |
| Emergency stop | Block | Blocked |

---

## Failure injection verified

| Injection | Safe degrade | Alerts / recovery | Unexpected orders |
| --- | --- | --- | --- |
| MT5 disconnect | Yes (chaos/cert) | Degraded health | None |
| Gateway offline | Yes | Degraded | None |
| Missing market data | Gate blocks | NO_TICKS alert path | None |
| Empty journal | Analytics unavailable (honest) | N/A | None |
| Calendar unavailable | Alert | CALENDAR_UNAVAILABLE | None |
| High latency / slow path | Degrade + alert | HIGH_LATENCY | None |
| Disk nearly full | Alert | DISK_USAGE | None |
| Database unavailable | Alert + chaos | DATABASE_UNAVAILABLE | None |
| Gateway/MT5 recovery | Safe reconnect + safe-read | `retry_order_send` raises | None |

Real Windows MT5 kill / Cloudflare tunnel cut remain **operational drills** (not claimed by unit chaos).

---

## Consistency

Auto Trading status builder and ops `HealthMonitor` share the same live probe snapshot in unit coverage (`test_auto_trading_status_sync` + acceptance consistency case). Operator still must confirm Monitoring ≡ Broker ≡ Auto Trading on the live desk before enabling automation.

---

## Audit trail

Required spine stages present: validation → risk → safety → submit. Certification pipeline links decision through OMS/gateway/MT5 to journal. Correlated fill linkage on live broker traffic remains an **operational prerequisite** (Demo cert / live journal review).

---

## Recovery

Peak equity HWM survives process restart via `.quantforg_state` / tracker persist path (unit). Kill switch arms and blocks Auto Trading. Duplicate execution identities survive export/import. Automatic `order_send` retry remains forbidden.

---

## Long-running stability

| Target | Status |
| --- | --- |
| Accelerated stress soak | PASS (CI-safe) |
| 24h wall-clock | **PENDING OPERATIONAL EVIDENCE** |
| 72h wall-clock | **PENDING OPERATIONAL EVIDENCE** |
| 7d wall-clock | **PENDING OPERATIONAL EVIDENCE** |

Command (dedicated host):

```bash
poetry run python scripts/institutional_soak.py --profile 24h --wall-seconds 86400
poetry run python scripts/institutional_soak.py --profile 72h --wall-seconds 259200
poetry run python scripts/institutional_soak.py --profile 72h --wall-seconds 604800
```

---

## Open items

### Engineering defects

_(None verified as defects in this acceptance pack. No trading-logic changes made.)_

### Operational prerequisites

1. Complete wall-clock soak 24h / 72h / 7d and archive JSON under `docs/production/reports/`
2. Live MT5 disconnect + gateway restart drill with Monitoring ≡ Broker ≡ Auto Trading
3. Demo certification trade before `EXECUTION_ENABLED=true`
4. Confirm peak equity file/DB on durable volume across API restarts
5. OWNER sign-off on Production Checklist
6. Confirm CI integration job green on release commit

### Future improvements

1. Persist regime labels on closed deals for production regime reports
2. Correlated request_id assertion from decision through fill in one integration fixture
3. Optional PDF export for period reports
4. Reconnect-count series on services-health from reliability timeline

---

## Acceptance status

| Option | Selected |
| --- | --- |
| Accepted | |
| **Accepted with Conditions** | **Yes** |
| Rejected | |

Conditions = operational prerequisites above. Engineering suite for scenarios/failures/consistency/recovery is green for controlled evaluation.
