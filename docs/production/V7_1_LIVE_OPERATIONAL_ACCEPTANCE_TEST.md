# QuantForg v7.1 Live Operational Acceptance Test (OAT)

Updated: `2026-07-29T01:25Z` (approx)

**Declaration: QUANTFORG v7.1 LIVE PRODUCTION NOT ACCEPTED**

Evidence under `docs/production/reports/oat_v71/`.

## Results

| Step | Item | Status | Evidence / notes |
|---|---|---|---|
| 1 | Full restart (FE/BE/Gateway/MT5) | **PARTIAL** | Gateway process recycle proven (PID change 8052→10988→8844); FE/Railway health ok. Full coordinated FE+Railway recycle still operator-confirmed. |
| 2 | MT5 reconnect | **PASS** | Live disconnect→attach recovery (`step2_*.json`). |
| 3 | Gateway restart | **PASS** | Operator admin restart completed; subsequent probes show single healthy listener + attached MT5. |
| 4 | Browser / PC restart | **FAIL** | No operator evidence yet. Agent browser cannot prove this. Checklist: `REMEMBER_ME_OPERATOR_CHECKLIST.md`. Soft fix: refresh preserves Remember Me preference. |
| 5 | 24h long run | **FAIL** | Soak ran ~23.99h but includes **305 disconnect samples** after `2026-07-28T12:38:14Z` with no self-heal until process recycle. RCA: `SOAK_DISCONNECT_RCA.md`. Gateway reconnect loop fix applied — **requires a fresh ≥24h soak** after deploying the fix. |

## Summary

- PASS: 2 (MT5 reconnect, gateway restart)
- PARTIAL: 1 (full stack)
- FAIL: 2 (Remember Me/PC restart; soak quality)

## Software fixes landed (not sufficient alone)

1. Gateway heartbeat no longer permanently abandons reconnect when `connected=false` (`services/mt5_gateway/runtime.py`)
2. Auth token refresh preserves Remember Me storage preference (`frontend/src/lib/api/client.ts`)

## Remaining blockers (must clear for acceptance)

1. Operator completes Remember Me checklist after **PC restart** with evidence files
2. Fresh ≥24h soak after gateway fix with disconnect self-heal verified
3. Re-declare PAT + OAT **ACCEPTED** only when steps above PASS

**Acceptance rule:** all OAT steps must be **PASS**. Until then, do **not** declare LIVE PRODUCTION ACCEPTED / do not push release to `main`.
