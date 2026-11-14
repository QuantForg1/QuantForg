# Phase 11 — Preparation + XM demo authentication evidence (2026-11-14)

**Scope:** Checklist sections A–B prep; **no** staging dispatch enablement; **no** Production multi-account LIVE.  
**`origin/main` tip at write:** `cbb6bdef` (PR #254 — honest `trade_allowed` gates).  
**Production + staging API `/api/v1/version`:** `cbb6bdefc9860f515f565c9a85c4596438f4bb00` · prod health `ok`.

## Hard locks (confirmed intent — not flipped)

```text
MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false   # Production must stay false
MULTI_ACCOUNT_DISPATCH_ENABLED            # staging NOT enabled (Owner approval pending)
QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false
FORCE_FIRST_TRADE=false
QUANTFORG_M1_MICRO_LIVE_SUBMIT=false
```

Weltrade Program Files LIVE terminal: **protected** (`weltrade_live_protected=true`, LIVE process observed). OMS / Policy v16 / SaaS / Billing / customer prefs: **not modified**.

## Prerequisite audit (checklist P1–P5)

| # | Prerequisite | Status | Evidence |
|---|---|---|---|
| P1 | Protected demo creds in `deploy/mt5_worker_agent/local.env` | **PARTIAL** | ACL tightened (`protect_local_env.ps1`). Presence check: **XM demo** `READY_TO_VERIFY`; Weltrade/Exness/HFM/JustMarkets/IC/Pepperstone/FP **demo** `BLOCKED_MISSING_CREDENTIALS`. All eight **LIVE** key triples `READY_TO_VERIFY` (presence only ≠ authenticated). |
| P2 | Staging API sealed-claim material | **NOT CHECKED / NOT REQUIRED YET** | Deferred until dispatch approval. |
| P3 | Written staging `MULTI_ACCOUNT_DISPATCH_ENABLED=true` | **PENDING Owner** | Explicitly **not** enabled this session. |
| P4 | Staging Railway on current `main` | **OPEN** | Staging version probe recorded separately; must re-confirm before section D. |
| P5 | Portable `demo-a` / `demo-b`; LIVE untouched | **PARTIAL** | `demo-a` exists + `terminal64.exe`. `demo-b` **absent**. Soft cap `max_concurrent_portables=1`. Disk ~2.76 GB. LIVE Program Files terminal **running** and outside portable budget. |

## Credential presence matrix (names/status only — no secrets)

Source: `.\deploy\mt5_worker_agent\check_broker_credentials.ps1` (exit 1 due to demo gaps; JSON `ok:true` with `blocked:7`).

| Broker | Demo | Live keys present |
|---|---|---|
| weltrade | BLOCKED_MISSING_CREDENTIALS | READY_TO_VERIFY |
| xm | READY_TO_VERIFY | READY_TO_VERIFY |
| exness | BLOCKED_MISSING_CREDENTIALS | READY_TO_VERIFY |
| hfm | BLOCKED_MISSING_CREDENTIALS | READY_TO_VERIFY |
| justmarkets | BLOCKED_MISSING_CREDENTIALS | READY_TO_VERIFY |
| ic-markets | BLOCKED_MISSING_CREDENTIALS | READY_TO_VERIFY |
| pepperstone | BLOCKED_MISSING_CREDENTIALS | READY_TO_VERIFY |
| fp-markets | BLOCKED_MISSING_CREDENTIALS | READY_TO_VERIFY |

## Authentication results (this session)

| Broker | Env | Slot | Real MT5 test | Result | Claim |
|---|---|---|---|---|---|
| **xm** | **demo** | **demo-a** | **Yes** | `mt5_verify_ok` · server `XMGlobal-MT5 2` · login_masked `***0464` · `trade_allowed=true` · `trade_expert=true` · `trade_mode=0` · `market_data_ok=true` · evidence `2026-11-14T12:22:53+00:00` | **DEMO VERIFIED** |
| Other demos | demo | — | Not run | Missing `QF_DEMO_<BROKER>_*` | **NOT VERIFIED** |
| All LIVE portable | live | — | Not run this session | Keys present only | **NOT VERIFIED** (do not reuse older conflicting docs as proof) |

Evidence file (host): `var/mt5_broker_verification.json` · source `windows_mt5_demo_verify` · passwords never written.

### Capacity snapshot

```json
{
  "max_concurrent_portables": 1,
  "prepared_slots": 1,
  "running_portables": 0,
  "live_terminal_running": true,
  "available_now": 1,
  "weltrade_live_protected": true,
  "new_vps_required": false
}
```

## Doc consistency note

- `EIGHT_BROKER_PRODUCTION_ACCEPTANCE_2026-11-14.md` records a later LIVE matrix with mixed `trade_allowed` outcomes.
- `MULTI_ACCOUNT_PHASE11_LIVE_ACCEPTANCE.md` records an earlier portable LIVE run with **0/8** `VERIFIED_LIVE` (`-6 Authorization failed`).
- **This Phase 11 prep report does not reconcile those historical claims.** Only the XM **demo** portable auth above is newly proven.

## Blockers (exact next Owner actions)

1. Fill missing **demo** triples in protected `local.env` for brokers still `BLOCKED_MISSING_CREDENTIALS` (or generic `QF_DEMO_LOGIN`/`PASSWORD`/`SERVER` if single-broker lab). **Do not paste values into chat.**
2. Optionally prepare `demo-b` when disk ≥ ~2 GB headroom and soft-cap policy allows (current soft cap is **1** concurrent portable).
3. Reply with **written approval** to set **staging-only** `MULTI_ACCOUNT_DISPATCH_ENABLED=true` before checklist section D.
4. Do **not** authorize Production multi-account LIVE in this phase.

## Workflow (operator — no secrets in chat)

```powershell
.\deploy\mt5_worker_agent\protect_local_env.ps1
# Owner fills QF_DEMO_* in local.env offline
.\deploy\mt5_worker_agent\check_broker_credentials.ps1
.\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker <slug> -Slot demo-a -Env demo
# After written staging dispatch approval ONLY:
#   set staging MULTI_ACCOUNT_DISPATCH_ENABLED=true
#   continue checklist D→F
```

`verify_demo_broker.ps1` now prefers `.venv` Python (same pattern as `check_broker_credentials.ps1`).

## Orders / mutations

- Orders submitted: **0**
- Staging dispatch enabled: **NO**
- Production multi-account LIVE enabled: **NO**
- Preference / Policy / billing changes: **NO**
