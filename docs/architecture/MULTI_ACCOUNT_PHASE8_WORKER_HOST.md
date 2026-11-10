# Multi-account Phase 8 — Worker host readiness + staging demo dispatch

**Status:** Host prep + staging lab enqueue path. LIVE fan-out **DISABLED**.  
**Depends on:** Phase 6.1 durable queue, Phase 7 ops snapshot, Windows MT5 worker agent.

## Safety locks (must remain false until Owner proof)

| Flag | Required value |
|---|---|
| `MULTI_ACCOUNT_DISPATCH_ENABLED` | `false` until staging demo auth + dispatch proven |
| `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` | `false` |
| `QUANTFORG_M1_MICRO_LIVE_SUBMIT` | `false` |
| `FORCE_FIRST_TRADE` | `false` |
| `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` | `false` |

`QF_DISPATCH_LAB_ENABLED` may be `true` on **staging only**. Lab enqueue is hard-forbidden when `APP_ENV=production`.

## Why `execution_workers=0`

Worker register/heartbeat persists to `mt5_worker_control_plane` (and the in-process control plane).  
`public.execution_workers` is the Phase-1a ownership-bound assignment table and can remain `0` until SaaS account provisioning writes rows. Ops summary exposes `control_plane_worker_count` + `execution_workers_note` so operators do not confuse the two.

## Host boundaries

- Portable slots: `C:\QuantForg-Workspace\mt5_worker_slots\{demo-a,demo-b}`
- LIVE Weltrade path: `C:\Program Files\MetaTrader 5\terminal64.exe` — refused by `paths.assert_not_live_terminal`
- Existing host only — no new VPS
- Demo broker credentials (`QF_DEMO_*`) remain Owner-supplied; never invent

## Staging lab enqueue

`POST /api/v1/mt5-workers/dispatch/lab-enqueue`

- Worker token required
- Bound to registered worker assignment
- Forces delivery-suppressed plan with `live_submit_allowed=false`
- Allowed when `APP_ENV=staging` (or non-prod + `QF_DISPATCH_LAB_ENABLED`)
- Forbidden in production even if lab flag is set

## Agent commands

```text
railway-ping
railway-register
railway-heartbeat
railway-dispatch-poll [--no-ack]
railway-dispatch-recover
```

Harness: `scripts/staging_phase8_dispatch_demo.py` (forces staging API URL).

## ITE integration

Not wired into `institutional_ite_runtime` until staging demo claim/ACK is proven and Owner authorizes flag changes. See `MULTI_ACCOUNT_PHASE8_ITE_CONTRACT.md`.
