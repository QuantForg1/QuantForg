# QuantForg v7.1 Production Acceptance Test (PAT)

Generated: `2026-07-30T17:16:12.732855+00:00`

**Declaration:** QUANTFORG v7.1 PRODUCTION NOT ACCEPTED — FAIL items must be fixed.

## Results

| Test | Status | Issues |
|---|---|---|
| TEST_1_SYSTEM_STARTUP | **BLOCKED** | full FE/BE/Gateway/MT5 restart cycle not executed in this harness (gw=True, api_prod=True, fe_port=False, be_port=False, profile=yes) |
| TEST_2_MT5_RECONNECT | **BLOCKED** | automatic reconnect code path verified; physical MT5 disconnect/reconnect not executed |
| TEST_3_GATEWAY_FAILURE | **BLOCKED** | gateway stop/start not executed by harness |
| TEST_4_MARKET_CLOSED | **PASS** | — |
| TEST_5_MULTI_ASSET | **PASS** | — |
| TEST_6_MAX_OPEN | **PASS** | — |
| TEST_7_POSITION_MANAGEMENT | **BLOCKED** | PME feature presence verified; live reconnect continuity not physically verified |
| TEST_8_SESSION | **BLOCKED** | browser refresh/restart/PC restart not executed in this harness |
| TEST_9_LONG_RUN | **FAIL** | soak duration 23.99h < required 24h (first=2026-07-27T18:35:38.2499607Z, last=2026-07-28T18:35:18.1603001Z, samples=908); soak evidence STALE — last sample age 46.68h > 2.0h (last_ts=2026-07-28T18:35:18.1603001Z). Claimed longer soaks on operator hosts are not present in accessible git/workspace evidence. |
| TEST_10_PERFORMANCE | **PASS** | — |

## Summary

- PASS: 4
- FAIL: 1
- BLOCKED: 5

Evidence JSON: `docs/production/reports/v7_1_pat_20260730T171612Z.json`

Acceptance rule: **all ten tests must be PASS** (no BLOCKED, no FAIL)
before declaring PRODUCTION ACCEPTED.
