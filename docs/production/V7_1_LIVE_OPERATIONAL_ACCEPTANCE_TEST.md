# QuantForg v7.1 Live Operational Acceptance Test (OAT)

Generated: `2026-07-27T18:36:00Z` (approx)

**Declaration: QUANTFORG v7.1 LIVE PRODUCTION NOT ACCEPTED**

No product code was changed. Evidence under `docs/production/reports/oat_v71/`.

## Results

| Step | Item | Status | Evidence / notes |
|---|---|---|---|
| 1 | Full restart (FE/BE/Gateway/MT5) | **FAIL** | Production FE `www.quantforg.com` = 200; Railway API = ok; broker profile present; MT5 attached on Weltrade-Real. **Gateway process restart failed** — PID 8052 is elevated (`Access is denied` on `taskkill` / `schtasks /RL HIGHEST`). Soft `Stop-Process` left same PID. Local ports 3000/8000 down (prod uses www + Railway). |
| 2 | MT5 reconnect | **PASS** | Live `POST /session/disconnect` → mid `connected=false`; `POST /session/attach` → poll0 `connected=true` / `session=attached` without manual broker setup. Logs: `step2_*.json`. |
| 3 | Gateway restart | **FAIL** | Cannot terminate elevated gateway from this agent session. Elevated scheduled task create also `Access is denied`. Heartbeat remained healthy on existing process; **process-level stop/start not proven**. |
| 4 | Browser / PC restart | **FAIL** | Agent browser opened `https://www.quantforg.com/login` (Remember Me UI present) — **session not restored** in this browser profile (login form shown). PC restart **not executed**. |
| 5 | 24h long run | **BLOCKED** | Read-only soak logger **started** (PID in `soak_24h.pid`), first samples written to `soak_24h_metrics.jsonl` / `soak_24h_latest.json`. **24 hours not elapsed** — cannot PASS yet. |

## Summary

- PASS: 1 (MT5 session reconnect)
- FAIL: 3 (full stack restart, gateway process restart, browser/PC session)
- BLOCKED: 1 (24h soak in progress)

## Live metrics (sample)

From `soak_24h_latest.json` at `2026-07-27T18:36:46Z`:

- Gateway HTTP latency: **104.53 ms**
- MT5 probe latency: **0.607 ms**
- MT5 connected / attached: **true**
- Heartbeat: present
- CPU sample: **72.98%**
- Gateway+terminal RAM sample: **38.21 MB**
- Railway health that sample: **timeout** (intermittent; earlier direct probe was `ok`)
- Soak process: **PID 5476** running (`soak_24h.pid`)

## Remaining blockers (must clear for acceptance)

1. **Admin restart of elevated gateway** — run as Administrator: stop PID on :8765, start `python -m services.mt5_gateway.main`, confirm auto-attach + heartbeat.
2. **Full stack restart proof** — confirm Railway backend recycle (Railway dashboard/CLI) and production FE deploy health after recycle; confirm no duplicate workers/orders.
3. **Operator browser session** — in the real browser profile with Remember Me: refresh, close/reopen, then **PC restart**; confirm still logged in + broker restore.
4. **Complete 24h soak** — leave `soak_24h.ps1` running; after 24h inspect `soak_24h_metrics.jsonl` for disconnects, memory growth, duplicate-order incidents (ops logs).

## What already passed live

- MT5 disconnect → attach recovery without manual login/setup
- Gateway + MT5 heartbeat healthy on Weltrade-Real after session reconnect
- Production FE and Railway API reachable
- Encrypted broker profile present on disk

---

**Acceptance rule:** all OAT steps must be **PASS**. Until then, do **not** declare LIVE PRODUCTION ACCEPTED.
