# QuantForg v7.1 Live Operational Acceptance Test (OAT)

Generated: `2026-07-30T11:47:23.511007+00:00`

**Declaration: QUANTFORG v7.1 LIVE PRODUCTION NOT ACCEPTED — see FAIL steps with live evidence.**

Re-audited against **live** Railway/FE probes and accessible soak artifacts.
Do not treat prior Jul 27 markdown as current.

## Results

| Step | Item | Status | Evidence / notes |
|---|---|---|---|
| 1 | Full restart (FE/BE/Gateway/MT5) | **FAIL** | Live FE ok=True; Railway ok=True; gateway :8765 from auditor ok=False. Full FE/BE/Gateway/MT5 restart cycle still not proven. |
| 2 | MT5 reconnect | **PASS** | {"prior_live_logs": ["step2_disconnect.json", "step2_attach.json", "step2_recovered.json"], "note": "Prior live disconnect\u2192attach PASS retained; cannot re-run without gateway access."} |
| 3 | Gateway restart | **FAIL** | {"gateway_reachable_from_auditor": false, "prior_oat": "Access denied on taskkill/schtasks for elevated gateway PID", "note": "Process-level stop/start still not proven in accessible evidence."} |
| 4 | Browser / PC restart | **FAIL** | {"prior_oat": "agent browser showed /login; PC restart not executed", "note": "No new Remember-Me / PC-restart witness in accessible evidence."} |
| 5 | 24h long run | **FAIL** | Accessible soak duration **16.162h** (first=2026-07-27T18:35:38.2499607Z, last=2026-07-28T10:45:19.9132149Z, n=505); last sample age **49.034h** (STALE). Claimed ~48h Windows soak is **not present** in git/workspace evidence. |

## Summary

- PASS: 1
- FAIL: 4
- BLOCKED: 0

## Live probes (this audit)

- Collected at: `2026-07-30T11:47:23.511007+00:00`
- Railway `/api/v1/health`: **ok**
- Railway `/api/v1/health/status`: **healthy**
- Frontend `www.quantforg.com`: **200**
- Local gateway `127.0.0.1:8765`: **unreachable from auditor**

## Soak evidence (accessible)

- Duration: **16.162 hours** (required ≥ 24)
- Samples: 505
- Window: `2026-07-27T18:35:38.2499607Z` → `2026-07-28T10:45:19.9132149Z`
- Age of last sample: **49.034 hours**
- Meets 24h: **False**; Meets 48h: **False**; Stale: **True**
- Gateway ok/bad: 504/1; MT5 connected samples: 504
- Railway ok/bad during soak: 238/267

## Remaining verified blockers

1. **OAT Step 1 FAIL** — full stack restart not proven; gateway unreachable from this auditor.
2. **OAT Step 3 FAIL** — elevated gateway process recycle still not proven.
3. **OAT Step 4 FAIL** — browser/PC Remember-Me restore still not proven.
4. **OAT Step 5 FAIL** — accessible soak is **16.16h** and **~49h stale**; claimed 48h soak not in accessible evidence.

JSON: `docs/production/reports/oat_v71/oat_latest.json`

**Acceptance rule:** all OAT steps must be **PASS**. Until then, do **not** declare LIVE PRODUCTION ACCEPTED.

