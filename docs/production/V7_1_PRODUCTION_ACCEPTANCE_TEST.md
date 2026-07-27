# QuantForg v7.1 Production Acceptance Test (PAT)

Generated: `2026-07-27T18:25:58.714173+00:00`

**Declaration:** QUANTFORG v7.1 PRODUCTION NOT ACCEPTED — BLOCKED live/operator verifications remain (reconnect soak, 24h run, browser/PC restart).

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
| TEST_9_LONG_RUN | **BLOCKED** | 24-hour continuous live run not executed — requires operator soak with witness/heartbeat evidence |
| TEST_10_PERFORMANCE | **PASS** | — |

## Summary

- PASS: 4
- FAIL: 0
- BLOCKED: 6

Evidence JSON: `docs/production/reports/v7_1_pat_20260727T182558Z.json`

Acceptance rule: **all ten tests must be PASS** (no BLOCKED, no FAIL)
before declaring PRODUCTION ACCEPTED.
