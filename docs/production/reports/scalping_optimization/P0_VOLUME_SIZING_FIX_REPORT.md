# P0 — Owner-Compliant Volume Sizing Fix

**Status:** Implemented locally — **not merged, not deployed** (awaiting explicit owner approval)  
**Date:** 2026-11-05  
**Branch:** `fix/p0-owner-volume-ceiling`  
**Inputs:** `QUANTFORG_LIVE_SCALPING_OPTIMIZATION_REPORT.md`, `SCENARIO_B_IMPLEMENTATION_READINESS.md`  
**Owner floors:** unchanged (max lot **0.01**, risk **20%**, min RR **0.20**, Q70, concurrent **1**, daily halt **48%**, aggregate **30%**, grid/martingale/averaging OFF, M1 LIVE OFF)

---

## 1. Root cause

LIVE HQ momentum near-misses sized to **volume 0.02** despite `OWNER_MAX_LOT = 0.01`.

### Causal chain

1. Strategy / SOE accepted `momentum_scalping` BUY (quality cleared).
2. Decision pipeline built `RiskEngineConfig` via `risk_config_from_ite(..., max_lot=live_max)` where `live_max` is broker `volume_max` (commonly **100**), **not** the owner ceiling.
3. RiskEngine `PERCENTAGE_RISK` targeting ~20% of live equity (~**$3.10** at equity **$15.52**) computed raw lots ≈ `3.10 / (stop × 100)` ≈ **0.024** for stop ≈ 1.27.
4. `normalize_lots_against_broker` rounded down to broker step **0.02** and allowed it because `max_lot` was the broker max.
5. Inclusive OWNER_SL_RISK then evaluated volume **0.02**:
   - `(1.267 + 0.424) × 100 × 0.02 ≈ $3.39 > $3.10` → **REJECT**
6. Message text “The lot cannot be reduced below 0.02” refers to the **sized** volume already chosen, not a true broker `volume_min` of 0.02. Historical Weltrade fills at **0.01** confirm broker min is 0.01.

### Why OWNER_MAX_LOT did not appear in NOC

RiskEngine’s inclusive planned-risk check rejected with `OWNER_SL_RISK` **before** the OMS / `evaluate_owner_entry` path that emits `OWNER_MAX_LOT`. The oversized lot never reached the owner entry guard.

### Before / after (LIVE near-miss geometry)

| Volume | Stop+spread example | Planned risk | Cap @ $15.52 (20%) | Outcome |
|---:|---|---:|---:|---|
| **0.02** (before) | 1.267+0.424 | **~$3.39** | $3.10 | FAIL OWNER_SL_RISK |
| **0.01** (after) | 1.267+0.424 | **~$1.70** | $3.10 | PASS OWNER_SL_RISK (lot legal) |

At current equity ~$22.63 the same 0.02 geometries could clear OWNER_SL_RISK cash-wise but would still violate max lot **0.01** — this fix blocks that path as well.

---

## 2. Fix design (authoritative boundary)

Single owner ceiling helper — **no second competing sizing system**:

- `owner_authorized_max_lot(broker_max)` → `min(broker_max, active_max_lot())`
- `owner_authorized_lot_ceiling_violated(...)` for broker-min > owner-max rejects

### Enforcement points

| Layer | Change |
|---|---|
| `risk_config_from_ite` | **Authoritative:** clamp `max_lot` to owner-authorized ceiling |
| Decision pipeline | Feasibility, RiskEngine rebuild, dynamic sizing v2, portfolio broker spec use owner-capped max |
| `RiskEngine.evaluate` (gold) | Reject if broker `min_lot` > owner max; defense-in-depth clamp of approved lots before OWNER_SL_RISK |
| `normalize_lots_against_broker` | Remains broker-faithful (callers pass owner-capped `max_lot`) |
| OMS / execution | Existing `min(live_max, OWNER_MAX_LOT)` retained |

After any clamp to 0.01, inclusive SL risk, planned-risk band, and downstream owner/OMS gates still run independently. If 0.01 fails any required constraint, the order is **rejected** (not forced).

---

## 3. Files changed

| File | Role |
|---|---|
| `app/domain/institutional_trading/owner_live_limits.py` | `owner_authorized_max_lot`, `owner_authorized_lot_ceiling_violated` |
| `app/application/services/institutional_decision_pipeline.py` | Clamp in `risk_config_from_ite` + live sizing call sites |
| `app/domain/institutional_trading/operations/min_lot_feasibility.py` | Normalize owner max clamp |
| `app/application/services/risk_engine.py` | Broker-min>owner reject; post-size clamp; normalize uses owner max |
| `app/domain/entities/risk_engine.py` | Allow config construct when broker min > owner max (reject in evaluate) |
| `tests/unit/test_p0_owner_volume_ceiling.py` | Regression suite |
| `docs/production/reports/scalping_optimization/P0_VOLUME_SIZING_FIX_REPORT.md` | This report |

---

## 4. Sizing flow (after fix)

```
Strategy signal
  → Strategy / AI sizing (already owner-aware where applicable)
  → Pipeline RiskEngineConfig.max_lot = owner_authorized_max_lot(broker_max)
  → RiskEngine.size_position → normalize_lots_against_broker (owner max belt)
  → RiskEngine.evaluate (OWNER_MAX_LOT / broker-min gate → OWNER_SL_RISK → …)
  → OMS / bridge (existing owner entry + execution safeguards)
  → MT5 Gateway / broker submit
```

Final executable volume **never exceeds 0.01**. Broker min/max/step still apply. Volume is never rounded **up** past the owner cap.

---

## 5. Tests

`tests/unit/test_p0_owner_volume_ceiling.py` (`unit` + `trading_core`):

- Planned 0.02 never survives when max_lot owner=0.01 (even if broker max=100)
- Valid 0.02 cash candidate at LIVE geometry normalizes to 0.01 and clears OWNER_SL_RISK
- OWNER_SL_RISK still rejects when inclusive risk at 0.01 exceeds 20%
- Broker min 0.02 > owner 0.01 → `OWNER_BROKER_MIN_EXCEEDS_MAX_LOT`
- Broker volume step respected under clamp
- Missing SL / volume 0.02 rejected by `evaluate_owner_entry`
- All five registry strategies share the same owner lot ceiling
- Forced `requested_lots=0.02` never approved above 0.01

**Local verification (this branch):**  
`pytest tests/unit/test_p0_owner_volume_ceiling.py --no-cov` → **10 passed**  
`ruff check` + `ruff format --check` on touched files → **clean**

---

## 6. Remaining blockers (fills / Scenario B)

1. Soft Scenario B thresholds still **not** implemented (by design until owner approval after this P0).
2. This fix unblocks the **lot legality** path for the documented near-miss cluster; it does **not** guarantee fills (ATR hard floor, RR, quality, session/gateway, concurrent=1 still apply).
3. Do **not** force the 17 historical signals into new trades.
4. Ops: intermittent `NO_SNAPSHOT` / gateway session waits remain separate P0 ops work.
5. Near-miss lifecycle still lacks persisted `OWNER_*` reason codes (analytics ticket from readiness report).

---

## 7. Rollback plan

1. Revert the PR / branch commit(s) touching the files listed above.
2. Redeploy previous Railway revision only after owner approval.
3. Confirm `OWNER_MAX_LOT` remains 0.01 and no temporary bypasses (`FORCE_FIRST_TRADE`, risk-lock overrides) were introduced (none in this change).

---

## 8. Explicit non-goals / guardrails honored

- Did **not** raise max lot, risk %, RR floors, quality floor, concurrent, daily halt, or aggregate risk.
- Did **not** enable grid / martingale / averaging / M1 LIVE.
- Did **not** place real-money test orders.
- Did **not** merge or deploy — **STOP** pending owner approval.
