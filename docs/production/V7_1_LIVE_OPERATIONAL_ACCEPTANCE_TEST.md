# QuantForg v7.1 Live Operational Acceptance Test (OAT)

Generated: `2026-07-30T11:56:24.631109+00:00`

**Declaration: QUANTFORG v7.1 LIVE PRODUCTION NOT ACCEPTED — see FAIL steps with live evidence.**

## Why soak still fails despite a live Windows gateway

Live `https://gateway.quantforg.com/health` proves the Windows host is up
(MT5 attached, heartbeat `2026-07-30T11:56:43.029048+00:00`).

But PAT/OAT Step 5 requires `docs/production/reports/oat_v71/soak_24h_metrics.jsonl`.
That file is written on Windows at:
`C:\Users\P7 PROVIDER\QuantForg\docs\production\reports\oat_v71\soak_24h_metrics.jsonl`
and has **not been imported into git** past `2026-07-28T10:45:19.9132149Z`.

See `docs/production/WINDOWS_SOAK_EVIDENCE_GAP.md`.

## Results

| Step | Item | Status | Evidence / notes |
|---|---|---|---|
| 1 | Full restart (FE/BE/Gateway/MT5) | **FAIL** | Live FE/Railway/gateway healthy; restart cycle not proven |
| 2 | MT5 reconnect | **PASS** | Prior step2 logs; live session=`attached` on Weltrade-Real |
| 3 | Gateway restart | **FAIL** | Process recycle not proven |
| 4 | Browser / PC restart | **FAIL** | No Remember-Me / PC-restart witness |
| 5 | 24h long run | **FAIL** | Accessible jsonl duration **16.162h**, last sample age **49.185h** (STALE). Claimed newer Windows soak **not imported** |

## Summary

- PASS: 1
- FAIL: 4
- BLOCKED: 0

## Live probes

- Railway health: **ok**
- Frontend: **ok**
- Public gateway: **ok** (`connected=True`, server=`Weltrade-Real`)
- Localhost :8765: **unreachable (expected off Windows host)**

## Remaining blockers

1. Import Windows `soak_24h_metrics.jsonl` / `soak_24h_latest.json` into git (`scripts/sync_windows_soak_evidence.ps1`)
2. Prove elevated gateway process restart
3. Prove browser/PC Remember-Me restore
4. Prove full stack restart without duplicate workers/orders

**Acceptance rule:** all OAT steps must be **PASS**.
