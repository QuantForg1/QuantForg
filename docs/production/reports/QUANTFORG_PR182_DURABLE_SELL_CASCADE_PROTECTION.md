# QUANTFORG PR #182 — Durable SELL Cascade Protection (LIVE)

**Date:** 2026-11-06  
**Owner approval:** Explicit for SELL cascade protection only  
**Baselines:** Trading `e4f15e40` (PR #180); audit docs `8d1f1ffe` (PR #181)  
**Instrument:** XAUUSD · Account in gap sample: **12479147**

---

## 1. Root cause of the PR #181 SELL cascade gap

PR #181 observed **eight consecutive broker-confirmed SELL stop-outs** (−25.22) after PR #180. Investigation showed:

| Factor | Finding |
| --- | --- |
| Broker exits | All eight tagged `[sl …]`; magic `260720`; comments `ite:v1:…` |
| Net P&L | profit + commission + swap; commission/swap fields 0; loss ≈ planned SL risk |
| PR #180 SELL store | **File-backed** JSON under data dir; **fail-open** when untrusted |
| Arming path | `record_losing_sell_close` existed but depended on `record_broker_confirmed_close` **or** a durable path that was not equivalent to BUY |
| PME/ITE close path | Called `record_losing_buy_close` on position-closed; **did not** call SELL record until this PR |
| Startup restore | BUY had `recover_buy_cascade_on_startup` + Postgres; SELL had **no** equivalent |
| Eligibility | Scoring called SELL evaluate but fail-open + missing anchors → **no block** |

**Exact reason seven subsequent SELL losses were not prevented:** after the first losing SELL, no durable trusted SELL anchor was restored into the LIVE eligibility gate, so unresolved same-direction SELL re-entry remained allowed.

---

## 2. The eight historical losses (broker attribution)

From PR #181 enriched evidence (account 12479147, post-`2026-11-06T09:51Z`):

| Position | Side | Net | Hold (s) | Approx planned risk | Close |
| --- | --- | --- | --- | --- | --- |
| 687174307 | SELL | −2.68 | 64 | 2.65 | SL |
| 687177072 | SELL | −4.28 | 90 | 4.23 | SL |
| 687180731 | SELL | −2.28 | 12 | 2.23 | SL |
| 687184354 | SELL | −3.62 | 1076 | 3.25 | SL |
| 687225893 | SELL | −5.38 | 1230 | 5.38 | SL |
| 687259338 | SELL | −1.76 | 61 | 1.59 | SL |
| 687268349 | SELL | −2.90 | 90 | 2.70 | SL |
| 687270993 | SELL | −2.32 | 149 | 2.32 | SL |

These tickets are the attribution set used to design backfill (broker history → arm unresolved SELL losses after last winning SELL).

---

## 3. Anchor creation and release rules

### Create (arm) — all required

- Direction **SELL**
- `fully_closed=True`
- `net_pnl < 0` (profit + commission + swap as supplied by broker evidence / PME close)
- Valid symbol, `position_id > 0`, `entry_price > 0`
- Idempotent on `(symbol, position_id)`

### Do not arm

- BUY closes, wins, partials, unconfirmed/missing prices, other accounts’ history without login match

### Block new SELL when

- Active anchor exists and proposed entry ≥ binding failed entry (binding = **min** active entry among anchors)
- Or store **untrusted** → `SELL_CASCADE_PROTECTION_UNAVAILABLE` (**fail closed** for SELL only)

### Release

- **Reclaim:** new SELL entry strictly **below** failed entry(s) → release anchors above that entry  
- **Bearish structure:** M1/M5 bearish BOS/CHOCH after `closed_at` (`bearish_reversal_since`) → release symbol  
- **Win / reconcile:** profitable broker net, still-open ticket, account mismatch, not-on-account under covered history

BUY is never blocked by SELL anchors.

---

## 4. PostgreSQL persistence

Table: `public.sell_cascade_anchor` (created via `CREATE TABLE IF NOT EXISTS` + RLS lockdown, same pattern as `buy_cascade_anchor`).

Columns: `symbol`, `position_id`, `entry_price`, `closed_at`, `net_pnl`, `close_outcome`, `status`, `release_reason`, `broker_login`, `created_at`, `updated_at`.

Primary key `(symbol, position_id)`; insert `ON CONFLICT DO NOTHING`.

Module: `app/domain/institutional_trading/ai_scalping/sell_cascade_anchor_store.py`.

---

## 5. Account / restart reconciliation

- `recover_sell_cascade_on_startup(adapter)` runs beside BUY recovery on ITE start  
- Restores active rows → reconciles open tickets / broker nets / account login  
- Backfills unresolved broker SELL losses after last winning SELL  
- Account mismatch releases foreign `broker_login` anchors  
- Missing Postgres / load failure → SELL gate fail-closed; BUY path untouched  
- Live adapter with unavailable broker history → store marked untrusted; new SELL blocked (`SELL_CASCADE_PROTECTION_UNAVAILABLE`) while anchors are retained

---

## 6. LIVE integration sequence

1. Broker/PME confirms close with net PnL  
2. `record_losing_sell_close` (ITE PME path + `record_broker_confirmed_close`)  
3. Durable row stored when loss+SELL+full close  
4. Startup/reconcile restores anchors  
5. Scoring `evaluate_durable_sell_cascade` before entry  
6. Unresolved SELL → explicit reject reason  
7. Bearish recovery / reclaim may release  
8. Surviving signals still pass Q70 / Risk / OMS  

No worker restart required beyond normal deploy. No test orders. No position mutation.

---

## 7. Tests and results

Added: `tests/unit/test_sell_cascade_anchor_store.py` covering:

1. Broker-confirmed losing SELL creates an anchor  
2. Duplicate close is idempotent  
3. Re-entry at/above failed entry blocked  
4. Bearish recovery / price reclaim releases  
5. Profitable SELL does not create a loss anchor  
6. Partial close ignored  
7. BUY not blocked by SELL anchors  
8. Account mismatch reconciled  
9. Restart restores active anchors  
10. Missing broker history fails closed for new SELL  
11. Database/persistence outage fails closed for SELL  
12–14. Existing BUY cascade, PR #180 reversal/OMS, and trading-core policy suites remain green  

Local: cascade + PR180 + trading-core related suites green (94+ in focused run; full CI on PR).

Owner policy assertions unchanged in existing trading-core tests.

---

## 8. Production feature configuration (verified after deploy)

| Item | Value |
| --- | --- |
| SELL cascade durable Postgres | **ON** — restore + backfill observed in Railway logs |
| BUY cascade | **ON** — restore trusted |
| LIVE execution | **ON** — worker RUNNING |
| LIVE reversal close | Unchanged (PR #180 default) |
| M1 evaluation | **ON** (`QUANTFORG_M1_MICRO_SCALPING=true`) |
| M1 LIVE submit | **OFF** (`QUANTFORG_M1_MICRO_LIVE_SUBMIT=false`) |
| Reverse entry | **OFF** |
| Risk 20% / halt 48% / lot 0.01 / Q70 / RR floors | **Unchanged** |

---

## 9. Verified deployment commit

| Check | Value |
| --- | --- |
| GitHub main | `5df0a87235e62f512101e0afb0349463a18e3efb` (Merge PR #182) |
| PR #182 | https://github.com/QuantForg1/QuantForg/pull/182 — CI green, merged |
| `/health.commit` | `5df0a87235e62f512101e0afb0349463a18e3efb` (matches main) |
| `/ready` | `ok` / `routers_registered` |
| Railway service | Online · deployment after merge |
| Worker | `worker_state=RUNNING` (ITE `run_forever`) |
| BUY cascade | `buy_cascade_startup_restore` trusted=True; backfill path active |
| SELL cascade | `sell_cascade_startup_restore` trusted=True; `sell_cascade_startup_recover` history_ok=True |
| SELL backfill | `sell_cascade_backfilled` count=9 on account **12479147** (includes PR #181 tickets 687174307…687270993) |
| M1 LIVE submit | Railway `QUANTFORG_M1_MICRO_LIVE_SUBMIT=false`; logs `m1_complement … submitted=False` |
| Reverse entry | Code path forced `live_reverse_entry_enabled=False` (unchanged) |
| LIVE trading | Remains enabled; no emergency-stop / force-first-trade overrides |

Production evidence is from Railway logs at deploy ~2026-11-06T11:11Z, not from unit tests alone.

**Note:** After backfill, scoring released the historical SELL anchors via `released_reversal` (bearish M1/M5 structure already present after those older closes). That matches documented release rules. Future broker-confirmed SELL losses will re-arm durable anchors and block unresolved re-entry until reclaim/reversal.

---

## 10. Remaining risks

1. First deploy must successfully create the table (Postgres available on Railway). If Postgres unavailable, SELL entries fail closed until store trusts again.  
2. Historical eight losses may be backfilled on startup if still in deal history and after last winning SELL — intentional protection, not a new trade.  
3. Reversal/M1 submit remain out of scope.  
4. Small samples still insufficient for profitability claims.

---

## 11. Owner policy confirmation

Risk 20% · Absolute 20% · Daily halt 48% · Max lot 0.01 · Q≥70 · Min RR 0.20 · Preferred 0.50 · Concurrent 1 · Aggregate 30% · Mandatory broker SL · No grid/martingale/averaging — **not modified**.

M1 LIVE submit **OFF**. Reverse entry **OFF**. Existing LIVE trading **left enabled**.
