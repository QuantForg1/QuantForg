# Multi-account Phase 8 — Worker host readiness + staging demo dispatch

**Status:** Host prep + staging lab enqueue path. LIVE fan-out **DISABLED**.  
**Depends on:** Phase 6.1 durable queue, Phase 7 ops snapshot, Windows MT5 worker agent.  
**Baseline:** `origin/main` @ `b0ee2de0` (Phase 7 merged).

## Safety locks (must remain false until Owner proof)

| Flag | Required value |
|---|---|
| `MULTI_ACCOUNT_DISPATCH_ENABLED` | `false` until staging demo auth + dispatch proven |
| `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` | `false` |
| `QUANTFORG_M1_MICRO_LIVE_SUBMIT` | `false` |
| `FORCE_FIRST_TRADE` | `false` |
| `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` | `false` |

`QF_DISPATCH_LAB_ENABLED` may be `true` on **staging only**. Lab enqueue is hard-forbidden when `APP_ENV=production`.

## Phase 8.1 — Windows host audit (existing host only)

| Check | Result |
|---|---|
| Host | Existing Windows MT5 host retained — **no new VPS** |
| LIVE terminal | `C:\Program Files\MetaTrader 5\terminal64.exe` present; `QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false` |
| Portable slots | `C:\QuantForg-Workspace\mt5_worker_slots\{demo-a,demo-b}` prepared (portable `terminal64.exe` each) |
| Scheduled tasks | `QuantForgMT5Gateway` Running; `QuantForgMT5Terminal` / `QuantForgVpsWatchdog` Ready |
| Worker agent config | Points to **staging** `QUANTFORG_API_BASE_URL`; token present (len≥16); no `QF_DEMO_*` in agent env |
| Staging heartbeats | **Verified** — `local-windows-1` / `demo-a` + `demo-b` heartbeats on staging ops summary |
| Staging readiness | `ready=false`, `account_login_verified` empty — demo MT5 auth **not** proven |
| Production workers | Control-plane hosts=`0`; stale/revoked rows only — agent does **not** heartbeat production |

### Why production reports `execution_workers=0`

1. Runtime heartbeats persist to `mt5_worker_control_plane`, not necessarily `public.execution_workers`.
2. The Windows agent `local.env` targets **staging**, so production receives no fresh heartbeats from this host.
3. Ops summary exposes `control_plane_worker_count` + `execution_workers_note` to avoid confusing the two tables.
4. Do **not** claim a production worker online without a fresh authenticated heartbeat on production.

## Staging lab enqueue

`POST /api/v1/mt5-workers/dispatch/lab-enqueue`

- Worker token required
- Requires heartbeat + (broker verify **or** staging lab attestation)
- Forces delivery-suppressed plan with `live_submit_allowed=false`
- Allowed when `APP_ENV=staging` (or non-prod + `QF_DISPATCH_LAB_ENABLED`)
- Forbidden in production even if lab flag is set (HTTP 403)

`POST /api/v1/mt5-workers/lab/attest-assignment` — staging-only after heartbeat.

## Sealed credentials

- `POST /api/v1/mt5-workers/credentials/claim` issues Fernet envelopes (no `password` JSON field)
- Requires heartbeat; rotates `claim_id`; TTL-limited unwrap; revoke clears active claim
- Material from verified login/server + vault/`QF_DEMO_*` on API host only — never invent

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

## Customer Multi-Account UX

- Existing Broker desk remains the connection surface (Design Freeze RC4).
- Customer API: `GET /api/v1/multi-account/dispatch/status` returns own jobs + blocked reasons; never fabricates worker online / verified states.
- Admin ops UI (Phase 7) remains owner-only.
- Frontend polish for eligibility chips waits on verified demo evidence — no fake Connected/Verified badges.

## Owner actions still required

1. Supply disposable **demo** MT5 credentials into protected host `local.env` (`QF_DEMO_*` or broker-specific keys) — never commit
2. Optionally set Railway staging `QF_DEMO_*` (API-side seal material) the same way
3. Run `connect-demo` on a portable slot and confirm `account_login_verified`
4. Approve staging lab enqueue proof, then staging-only `MULTI_ACCOUNT_DISPATCH_ENABLED=true`
5. Separate written approval naming `institutional_ite_runtime` before ITE wiring
