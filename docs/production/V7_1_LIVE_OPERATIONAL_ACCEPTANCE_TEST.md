# QuantForg v7.1 Live Operational Acceptance Test (OAT)

Updated: `2026-07-30T13:25Z`

**Declaration: QUANTFORG v7.1 LIVE PRODUCTION NOT ACCEPTED**

Evidence under `docs/production/reports/oat_v71/`.

## Results

| Step | Item | Status | Evidence / notes |
|---|---|---|---|
| 1 | Full restart (FE/BE/Gateway/MT5) | **PARTIAL** | Gateway process recycle proven (PID change 8052→10988→8844); FE/Railway health ok. Full coordinated FE+Railway recycle still operator-confirmed. |
| 2 | MT5 reconnect | **PASS** | Live disconnect→attach recovery (`step2_*.json`). |
| 3 | Gateway restart | **PASS** | Operator admin restart completed; subsequent probes show single healthy listener + attached MT5. |
| 4 | Browser / PC restart | **FAIL** | No operator evidence yet. Checklist: `REMEMBER_ME_OPERATOR_CHECKLIST.md`. |
| 5 | 24h long run | **FAIL** | Prior soak ~23.99h with unmanaged disconnect window. Reconnect fix landed in git (gateway **1.1.1**) — requires fresh ≥24h soak after Windows deploy. RCA: `SOAK_DISCONNECT_RCA.md`. |

## Summary

- PASS: 2 (MT5 reconnect, gateway restart)
- PARTIAL: 1 (full stack)
- FAIL: 2 (Remember Me/PC restart; soak quality)

## Software fixes

1. Gateway reconnect-loop fix landed (`services/mt5_gateway/runtime.py`, gateway **1.1.1**). PAT/OAT remain **NOT ACCEPTED**.
2. Remember Me soft fix still requires operator PC-restart evidence (`step4_remember_me_*.json`).

## Remaining blockers (must clear for acceptance)

1. Deploy gateway 1.1.1 on Windows and complete **post-fix** ≥24h soak with disconnect self-heal verified
2. Operator completes Remember Me checklist after **PC restart** with evidence files
3. Re-declare PAT + OAT **ACCEPTED** only when steps above PASS

**Acceptance rule:** all OAT steps must be **PASS**. Until then, do **not** declare LIVE PRODUCTION ACCEPTED / do not push release to `main`.
