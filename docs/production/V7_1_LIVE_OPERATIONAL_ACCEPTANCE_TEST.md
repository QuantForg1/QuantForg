# QuantForg v7.1 Live Operational Acceptance Test (OAT)

Updated: `2026-07-30T17:18Z`

**Declaration: QUANTFORG v7.1 LIVE PRODUCTION NOT ACCEPTED**

Evidence under `docs/production/reports/oat_v71/`.  
Latest ops stop: `PRODUCTION_OPS_VERIFY_20260730T1718Z.md`.  
PAT re-run: `v7_1_pat_20260730T171612Z.json` — **NOT ACCEPTED**.

## Results

| Step | Item | Status | Evidence / notes |
|---|---|---|---|
| 1 | Full restart (FE/BE/Gateway/MT5) | **PARTIAL** | Gateway process recycle proven earlier; FE/Railway health ok. Full coordinated FE+Railway recycle still operator-confirmed. |
| 2 | MT5 reconnect | **PASS** | Live disconnect→attach recovery (`step2_*.json`). Live `/health` now `connected=true` / `attached`. |
| 3 | Gateway restart | **PASS** | Operator admin restart completed; live gateway `1.1.3` healthy. |
| 4 | Browser / PC restart | **FAIL** | No operator evidence yet. Checklist: `REMEMBER_ME_OPERATOR_CHECKLIST.md`. |
| 5 | 24h long run | **FAIL** | Synced soak still 23.99h and **stale** (PAT `TEST_9_LONG_RUN` 2026-07-30T17:16Z). Need fresh ≥24h soak after reconnect/1.1.3. |

## Summary

- PASS: 2 (MT5 reconnect, gateway restart)
- PARTIAL: 1 (full stack)
- FAIL: 2 (Remember Me/PC restart; soak quality)

## Software fixes (landed; acceptance still blocked)

1. Gateway reconnect + import/auth fixes on production (`1.1.3`); PR #38/#39 on Railway `main`.
2. Remember Me soft fix still requires operator PC-restart evidence (`step4_remember_me_*.json`).

## Remaining blockers (must clear for acceptance)

1. **OWNER:** Railway `EXECUTION_ENABLED=true` + caller token match — unverifiable without Railway/ops auth (`PRODUCTION_OPS_VERIFY_20260730T1718Z.md`)
2. **OWNER:** Authenticated `/ite/ops/auto-trading` cycle trace → first `primary_blocker` / OMS→MT5 proof
3. Windows: complete **post-fix** ≥24h soak and sync via `scripts/sync_windows_soak_evidence.ps1`
4. Operator: Remember Me Step 4 evidence files (`step4_remember_me_*.json`)
5. Re-declare PAT + OAT **ACCEPTED** only when steps above PASS with verified evidence

**Acceptance rule:** all OAT steps must be **PASS**. Until then, do **not** declare LIVE PRODUCTION ACCEPTED.
