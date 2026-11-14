# Phase 12A — Registry reconciliation + Production worker onboarding

**Status:** Audit complete · dual registry **intentional** · Production workers **not** dispatch-ready  
**Safety:** Keep `live_submit_armed_refused`. Do not wire multi-account OMS. Do not touch Weltrade LIVE Program Files.

---

## 1. Dual registry — intended responsibilities

| Registry | Table | Authoritative for | Written by |
|---|---|---|---|
| **Control plane** | `public.mt5_worker_control_plane` | Windows agent host/slot, lifecycle, heartbeat, login/server verify evidence | Worker register / heartbeat / verification report APIs |
| **Assignment registry** | `public.execution_workers` | Phase-1a ownership-bound assignment rows (customer account ↔ worker code) | Ownership-bound provisioning paths (not the lab/agent register path) |

Ops already states this via `execution_workers_note` and `control_plane_worker_count`.

### Field mapping (conceptual)

| Concern | `mt5_worker_control_plane` | `execution_workers` |
|---|---|---|
| Primary key | `worker_id` | `id` |
| User | `user_id` (nullable for lab UUIDs) | `user_id` NOT NULL → `users` FK |
| Account | `broker_account_id` (nullable lab) | `broker_account_id` NOT NULL → `broker_accounts` FK |
| Host/slot | `host_code` + `slot_id` (required) | not first-class (metadata only) |
| Lifecycle | `lifecycle_status` (ready/error/revoked/…) | `status` (registered/healthy/offline/…) |
| Heartbeat | `last_heartbeat_at` | `last_heartbeat_at` |
| Verify evidence | `account_login_verified`, `server_verified` | none |
| Credentials | **never stored** | **never stored** |

### Why Production shows control-plane=6 and execution_workers=0

1. The Windows agent `local.env` sets `QUANTFORG_API_BASE_URL` to **Staging**.  
2. Historical Production control-plane rows remain from earlier lab/register experiments; heartbeats stopped (stale since 2026-11-09/10).  
3. Agent register/heartbeat persists to **control plane**, not `execution_workers`.  
4. `execution_workers` stays empty until an ownership-bound provisioner writes FK-valid user/account rows.

**Authoritative for runtime readiness today:** `mt5_worker_control_plane` (+ in-process hydrate).  
**Do not auto-backfill** control-plane rows into `execution_workers` — lab synthetic UUIDs would violate FKs / uniqueness and create competing truth.

**Synchronization required?** No automatic sync. Optional future Owner-approved provisioner may insert `execution_workers` **only** for real owned accounts after verify — out of Phase 12A scope.

---

## 2. Production worker onboarding procedure (portable only)

Prerequisites (Owner):

1. Dedicated decision: heartbeats may target **Production** API for multi-account portable slots.  
2. Keep `QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false`.  
3. Never use `C:\Program Files\MetaTrader 5\` (Weltrade LIVE singleton).  
4. Keep `FORCE_FIRST_TRADE=false`, `QUANTFORG_M1_MICRO_LIVE_SUBMIT=false`.  
5. Keep multi-account OMS fan-out unwired (`live_submit_armed_refused`).

Steps (evidence-based; do not fabricate verify):

```text
1. Prepare portable slot under QF_MT5_SLOT_ROOT (e.g. demo-a) with its own terminal64.exe
2. Point a *Production* agent env (separate from Staging local.env):
     QUANTFORG_API_BASE_URL=https://quantforg-production.up.railway.app
     WORKER_SERVICE_TOKEN=<production worker token>
     QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false
3. railway-register + railway-heartbeat for that slot only
4. connect-demo / verify with disposable DEMO credentials from protected env
5. Confirm ops worker: lifecycle=ready, dispatch_ready=true,
   account_login_verified + server_verified set, not_ready_reasons=[]
6. Confirm Weltrade LIVE Program Files session untouched
7. Do NOT enable multi-account order_send
```

Staging workers are **not** Production-ready by copying rows.

---

## 3. JWT / Supabase authorities

| Env | Supabase host (from Railway vars) |
|---|---|
| Production | `otqyhlmwaifokrczryrc.supabase.co` |
| Staging | `saxsyobktmlyjghumxfz.supabase.co` |

**Separate projects by design.** A Production-minted Owner JWT returning **401** on Staging is **expected**. Do not share Production service-role keys with Staging or weaken JWT validation.
