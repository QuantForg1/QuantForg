# Phase 12B — Multi-Account OMS Execution Acceptance

**Date (UTC):** 2026-11-15  
**Merged PR #277:** `bf92df453df4e7b1c1da52f9f5e0c39c89635579`  
**Merged PR #283:** `7bc43aca88dd7f58fe2f11e802a7f7ab2ff0ca85`  
**Railway Production health (fill-acceptance check):** `7bc43aca88dd` / status ok  

| Gate | Status |
|---|---|
| Code complete (authorize → send → result) | **PASS** |
| CI / merge / deploy | **PASS** |
| Real DEMO broker reject evidence (`10027`) | **PASS** |
| DEMO fill ticket + reconciled position | **BLOCKED** |
| LIVE multi-account order_send | **PASS (fail-closed)** — 0 real-money submits |

---

## 1. Fill-acceptance terminal verification (2026-11-15)

| Check | Result |
|---|---|
| Host / slot | `prod-windows-1` / `demo-a` |
| Configured portable exe | `C:\QuantForg-Workspace\mt5_worker_slots_production\demo-a\terminal64.exe` (exists) |
| Production slot process running | **false** at probe time |
| Attached MT5 session path | `C:\QuantForg-Workspace\mt5_worker_slots\demo-a` |
| Account login | `169740464` → masked `***0464` |
| Server | `XMGlobal-MT5 2` |
| Identity match (XM DEMO target) | **PASS** |
| Account `trade_mode` | `0` (DEMO) |
| Account `trade_allowed` | **true** |
| Account `trade_expert` | **true** |
| Terminal Algo Trading (`terminal_info.trade_allowed`) | **false** |
| Terminal `tradeapi_disabled` | **false** |
| `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` | **false** |
| Weltrade Program Files LIVE used | **No** |
| Worker `dispatch_ready` | **true** (fresh heartbeat) |
| GOLD market | bid/ask present (`3882.55` / `3883.08`), `trade_mode=4` |
| Open GOLD positions before attempt | none |

**Blocker:** Algo Trading is still disabled on the attached portable DEMO terminal (`terminal_trade_allowed=false`). Per Owner instruction, **no new order was submitted**.

---

## 2. Prior Production DEMO broker evidence (still valid)

| Item | Value |
|---|---|
| Worker id | `5fb08249-eb47-459a-8ae9-61b38237f974` |
| Intent | `92fd3cb7-8511-43cd-9382-ac1cc117ec45` |
| OMS authorize | PASS (`order_send_allowed=true`) |
| Symbol path | `XAUUSD` → XM `GOLD` |
| Broker retcode | `10027` |
| Broker comment | `AutoTrading disabled by client` |
| OMS job state | `rejected` |
| Duplicate re-authorize | blocked (`intent_terminal`) |
| Broker ticket | none (reject) |
| Reconciled fill position | none (reject) |

That run proves OMS → worker → MT5 → broker response recording. It is **not** a fill.

---

## 3. Reconciliation / retry policy for this fill attempt

| Check | Status |
|---|---|
| Blind retry of prior UNKNOWN | **Not performed** |
| New order while AutoTrading off | **Not performed** (stopped) |
| LIVE flags / Weltrade LIVE | untouched / unused |

---

## 4. DEMO fill acceptance fields

| Field | Status |
|---|---|
| Actual terminal verification | **PASS** (identity + flags above) |
| `trade_allowed` (terminal Algo Trading) | **FAIL** (`false`) |
| Actual order submission (this session) | **NOT ATTEMPTED** |
| Broker ticket | **NOT TESTED** |
| Actual position | **NOT TESTED** |
| OMS reconciliation of fill | **NOT TESTED** |
| Duplicate protection (prior reject intent) | **PASS** |
| LIVE remained disabled | **PASS** |

---

## 5. Owner action required

1. Open the portable XM DEMO terminal used for `demo-a` (attached session under `mt5_worker_slots\demo-a`, configured production root `mt5_worker_slots_production\demo-a`).  
2. Confirm login `***0464` / server `XMGlobal-MT5 2`.  
3. Enable **Algo Trading** (toolbar AutoTrading) so `terminal_info.trade_allowed` becomes `true`.  
4. Keep the portable process running, then re-run the single 0.01 GOLD DEMO fill acceptance.  

Do not bypass AutoTrading via code. Do not use Program Files Weltrade LIVE.

---

## 6. Verdict

**DEMO fill acceptance: BLOCKED** — AutoTrading still disabled by client.  
Phase 12B code/deploy/reject-path evidence remains **PASS**. LIVE multi-account send remains **fail-closed**.
