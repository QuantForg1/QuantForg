# QuantForg v7.1 Production Acceptance Test (PAT)

Generated: `2026-07-30T12:37:03.739625+00:00`

**Declaration:** QUANTFORG v7.1 PRODUCTION NOT ACCEPTED — FAIL items must be fixed.

## Results

| Test | Status | Issues |
|---|---|---|
| TEST_9_LONG_RUN | **FAIL** | soak duration 23.99h < required 24h (first=2026-07-27T18:35:38.2499607Z, last=2026-07-28T18:35:18.1603001Z, samples=908); soak evidence STALE — last sample age 42.03h > 2.0h (last_ts=2026-07-28T18:35:18.1603001Z). Claimed longer soaks on operator hosts are not present in accessible git/workspace evidence. |

## Summary

- PASS: 0
- FAIL: 1
- BLOCKED: 0

Evidence JSON: `docs/production/reports/v7_1_pat_20260730T123703Z.json`

Acceptance rule: **all ten tests must be PASS** (no BLOCKED, no FAIL)
before declaring PRODUCTION ACCEPTED.
