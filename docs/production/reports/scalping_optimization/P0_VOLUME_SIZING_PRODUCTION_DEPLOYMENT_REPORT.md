# P0 Volume Sizing Fix — Production Deployment Report

**Status:** MERGED + DEPLOYED + VERIFIED  
**Date (UTC):** 2026-11-05  
**PR:** https://github.com/QuantForg1/QuantForg/pull/155  
**Feature commit:** `190997ed2f0ae5e663e8d96b276a411f378ec43f`  
**Merge commit on `main`:** `fe61db885438b1119d233923d405e18c2979ca35`

---

## 1. PR merge

| Item | Value |
|---|---|
| State | **MERGED** |
| Merged at | 2026-11-05T12:32:12Z |
| Merge method | merge commit |
| Merge SHA | `fe61db885438b1119d233923d405e18c2979ca35` |
| Ancestor check | `190997ed` is ancestor of `origin/main` |
| Frontend files in PR | **None** (backend/risk/docs/tests only) |

---

## 2. CI results (PR head `190997ed`)

| Check | Result |
|---|---|
| Design Governance Docs | SUCCESS |
| Lint & Format | SUCCESS |
| Type Check | SUCCESS |
| Unit Tests | SUCCESS |
| Trading Core Regression | SUCCESS |
| Frontend Lint Typecheck Build | SUCCESS |
| Integration Tests | SUCCESS |
| Vercel – frontend / quant-forg (preview) | SUCCESS |
| Supabase Preview | SKIPPED |

Local pre-merge: owner-policy constant check `POLICY_OK` (max_lot 0.01, risk 20%, RR 0.20, Q70, concurrent 1, daily 48%, agg 30%); P0 + owner suites green; `trading_core` 2050 passed.

---

## 3. Railway production deployment

| Item | Value |
|---|---|
| Project | QuantForg (`76f9026d-362f-4e16-961d-44e7a090459a`) |
| Environment | production (`cb96aa83-7ace-470a-9e98-d52a1634a446`) |
| Service | QuantForg (`b32863f9-2dce-4902-b32f-56963729f142`) |
| Source | `QuantForg1/QuantForg` · branch **`main`** |
| Deployment ID | `a956c2d3-426d-4821-948f-35aa74b18083` |
| Deployed commit | **`fe61db8`** (merge of PR #155) |
| Status | **SUCCESS** |
| Domain | https://quantforg-production.up.railway.app |
| Region | sfo |

Pipeline: merge → Railway auto-build/deploy of `main` → SUCCESS. No manual redeploy required. No unrelated services changed.

---

## 4. Vercel / frontend

No frontend product code in PR #155. **No production frontend redeploy triggered or required.**  
Vercel preview checks on the PR branch were SUCCESS only (not a production promotion).

---

## 5. Production health & LIVE evidence

### Public HTTP

| Endpoint | Status |
|---|---|
| `GET /health` | **200** `{"status":"ok"}` |
| `GET /ready` | **200** routers complete (100 registered, 0 failed) |
| `GET /api/v1/health` | **200** |
| `GET /api/v1/ready` | **200** |
| `GET https://gateway.quantforg.com/health` | **200** (`mt5-gateway` 1.2.0, token configured, execution enabled) |

### Railway deploy logs (post-`a956c2d3`, ~12:38Z)

| Check | Evidence |
|---|---|
| Scheduler / worker | `Scheduler Tick` · `mode=LIVE` · `run_state=running` · `worker_state=RUNNING` · `execution_enabled=True` |
| MT5 Gateway | Repeated `GET gateway.quantforg.com/health|positions|account|candles|quotes` → **200** |
| Weltrade sync | Account `Weltrade-Real`, equity/balance **$18.05**, positions `[]`, position recovery complete |
| Broker session | `BROKER_SESSION_OPEN` · `trade_allowed=True` · `safety_allowed=True` |
| Risk Engine | Active rejects: `min_lot 0.01` · `hard_max=20.0%` · `MIN_LOT_EXCEEDS_RISK_BUDGET` / `OWNER` planned-risk path · **do not upsize** |
| OMS | `forwarded_to_oms=False` when Risk blocks · `OMS Submit … NOT_ATTEMPTED` |
| Lot ceiling in LIVE path | Risk messages cite **`min_lot 0.01`** (not 0.02); no evidence of executable volume above owner max |
| M1 LIVE | `m1_complement … submitted=False` |
| Kill switch / false halt | `run_state=running` · cycles continue · no kill-switch activation observed |
| Forced trades | None placed for verification |

**Authenticated admin/policy JSON probe:** local `.env` has empty `SUPABASE_*` / no `QUANTFORG_OWNER_TOKEN`, so owner JWT could not be minted from this workstation. LIVE safeguards were verified from Railway runtime logs + public health instead.

---

## 6. Owner policy confirmation (unchanged)

Code on `main` still defines:

| Policy | Value |
|---|---|
| `OWNER_MAX_LOT` | **0.01** |
| Planned risk ceiling | **20%** |
| Min net RR | **0.20** |
| Min trade quality | **70** |
| Max concurrent | **1** |
| Daily loss halt | **48%** |
| Aggregate open risk | **30%** |
| Grid / martingale / averaging | OFF (unchanged) |
| M1 LIVE submissions | OFF (runtime `submitted=False`) |

`risk_config_from_ite` clamps broker `volume_max` through `owner_authorized_max_lot` so broker max cannot override the owner ceiling.

---

## 7. Remaining operational notes (not blockers)

1. Micro equity (~$18) still causes legitimate `MIN_LOT_EXCEEDS_RISK_BUDGET` when structural stop > affordable max at **0.01** lot — expected owner protection, not a regression.
2. Scenario B soft thresholds remain **not** implemented (separate approval).
3. Restore local Supabase/owner token in `.env` if future authenticated ops probes are needed from this machine.

---

## 8. Rollback

Redeploy Railway deployment `1b0ad18a` (prior SUCCESS on `52b2373`) or revert merge `fe61db88` on `main` and let production redeploy — only with explicit owner approval.
