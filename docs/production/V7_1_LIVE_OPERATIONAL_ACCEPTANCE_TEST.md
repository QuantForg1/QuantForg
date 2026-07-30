# QuantForg v7.1 Live Operational Acceptance Test (OAT)

Updated: `2026-07-30T12:37Z` — re-verified against Windows soak sync commit `9837123` (`cursor/v7-1-acceptance-evidence`).

**Declaration: QUANTFORG v7.1 LIVE PRODUCTION NOT ACCEPTED**

Evidence under `docs/production/reports/oat_v71/`.

## Results

| Step | Item | Status | Evidence / notes |
|---|---|---|---|
| 1 | Full restart (FE/BE/Gateway/MT5) | **PARTIAL** | Gateway process recycle proven (PID change 8052→10988→8844); FE/Railway health ok. Full coordinated FE+Railway recycle still operator-confirmed. |
| 2 | MT5 reconnect | **PASS** | Live disconnect→attach recovery (`step2_*.json`). |
| 3 | Gateway restart | **PASS** | Operator admin restart completed; subsequent probes show single healthy listener + attached MT5. |
| 4 | Browser / PC restart | **FAIL** | No `step4_remember_me_*.json` evidence. Checklist: `REMEMBER_ME_OPERATOR_CHECKLIST.md`. Soft fix: refresh preserves Remember Me preference. |
| 5 | 24h long run | **FAIL** | Synced soak is **pre-fix** (`2026-07-27T18:35Z`→`2026-07-28T18:35Z`): duration **23.994h**, **~42h stale**, **305** disconnect samples, **0** reconnects, ~5.95h unmanaged window. Reconnect-loop fix was **documented but never committed/deployed** (`should_beat` gate still present). Classification: `SOAK_POST_FIX_CLASSIFICATION.md`. **Requires post-fix ≥24h soak.** |

## Summary

- PASS: 2 (MT5 reconnect, gateway restart)
- PARTIAL: 1 (full stack)
- FAIL: 2 (Remember Me/PC restart; soak quality)
- PAT `TEST_9_LONG_RUN`: **FAIL** (`docs/production/reports/v7_1_pat_20260730T123703Z.json`)

## Software fixes

1. Gateway reconnect-loop fix: **NOT LANDED** in git (docs previously over-claimed). Defect still in `services/mt5_gateway/runtime.py`.
2. Remember Me soft fix: still requires operator PC-restart evidence (`step4_remember_me_*.json`).

## Remaining blockers (must clear for acceptance)

1. Land + deploy gateway reconnect-loop fix, then run **post-fix** ≥24h soak with disconnect self-heal verified
2. Operator completes Remember Me checklist after **PC restart** with evidence files
3. Re-declare PAT + OAT **ACCEPTED** only when steps above PASS

**Acceptance rule:** all OAT steps must be **PASS**. Until then, do **not** declare LIVE PRODUCTION ACCEPTED / do not push release to `main`.
