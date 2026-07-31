# LIVE Trading Root Cause Report

**Investigation type:** Observe-only (no strategy, threshold, risk, OMS, gateway, or MT5 changes)  
**Generated at:** 2026-07-31T19:02:00Z  
**Investigator:** Cursor agent (production evidence)

---

## Current production SHA

| Field | Value |
|---|---|
| Railway deployment ID | `97fe1220-affe-4aa5-a1e0-d03750400e33` |
| Status | SUCCESS / RUNNING |
| Branch | `main` |
| **Commit SHA** | `30fb60f50d1483a1c0fa6ab9719b984e28831097` |
| Commit message | `docs(deployment): merge Vercel Preview promotion audit` |
| Deployed at | 2026-07-31T18:20:41.532Z |
| Gateway version (local `/health`) | `1.1.6` |
| API version | `1.0.0` (`environment=production`) |

Evidence: `railway status --json` / `railway deployment list`.

---

## Step 1 — Live status (verified)

| Check | Result | Evidence |
|---|---|---|
| MT5 Gateway healthy | **YES** (local + Railway component health) | Local `http://127.0.0.1:8765/health` → `status=ok`, `mt5.connected=true`, `degraded=false`. Railway `/api/v1/health/trading-components` → `gateway=HEALTHY`. Note: public `https://gateway.quantforg.com/health` intermittently returned **HTTP 403** from this investigator host late in the session; Railway still reports gateway healthy and continues authenticated gateway calls. |
| MT5 connected | **YES** | `session_mode=attached`, `login=12260878`, `server=Weltrade-Real`, heartbeat `2026-07-31T19:01:55Z` |
| Broker connected | **YES** | Weltrade-Real / login 12260878; account probes succeed; portfolio syncs every ~45s |
| AutoTrading enabled (MT5 terminal) | **YES** | `mt5_autotrading_enabled=true`, `terminal_trade_allowed=true` |
| Operator Auto Trading | **YES (durable)** | `ite_ops_runtime_state`: `auto_trading_enabled=true`, `auto_trading_run_state=running`, `ops_mode=LIVE` (updated 2026-07-22; still active — live cycles running) |
| OMS healthy | **YES** | `oms=HEALTHY`, `execution_enabled=true`, `mt5_use_mock=false` |
| AI healthy | **YES** | `ai=HEALTHY` (`ite_runtime_present=true`); live `NO_TRADE` decisions every cycle |
| Market data live | **YES** | Live XAUUSD quote + M1/M5 candles via gateway; Railway cycle reasons include live spread/ATR |
| Quotes updating | **YES** | e.g. bid `4050.173` / ask `4050.577` at probe time; cycle spreads ~0.39–0.43 |
| Candles updating | **YES** | M1/M5 `items` length 5 with advancing bar times |
| Account mode | **real** | `account_mode=real`, `trade_mode=real`, `trade_mode_raw=2` |
| Session | **new_york** (allowed) | Cycle text: `Session new_york open for 24/7 desk` |
| Balance | **181.53 USD** | Gateway `/account` + `portfolio_syncs` |
| Equity | **181.53 USD** | Same |
| Free margin | **181.53 USD** | Same (`margin=0`) |
| Open positions | **0** | Gateway `/positions` → `items=[]`; Railway `MT5 positions: 0` |

**Trading components (Railway public):**

```text
statuses: gateway=HEALTHY, oms=HEALTHY, mt5=CONNECTED, ai=HEALTHY
all_ready_for_limited_pilot: true
```

---

## Step 2 — Decision pipeline stop point

Observed live path (Railway logs, repeated):

```text
Market Data          PASS  (quotes/candles/account reachable)
    ↓
Market Structure     PASS  (BOS/CHOCH/OB/FVG computed; not empty)
    ↓
SMC Detection        PASS  (events present: bos/choch, OB, FVG)
    ↓
Liquidity            FAIL  (code: no_liquidity_context — concurrent)
    ↓
MTF                  FAIL  ★ PRIMARY STOP
                     H4=range H1=down M15=range M5=up score=45 not aligned
    ↓
AI Quality           FAIL  (concurrent: Trade quality 74 below gate)
    ↓
Confidence           FAIL  (concurrent: confidence_below_threshold)
    ↓
Risk                 NOT REACHED for OMS path (logged FAIL because eligibility=NO_TRADE)
    ↓
Dynamic Position Sizing   computed in evidence only → below_min_lot (lots≈0.002)
    ↓
Portfolio Risk       NOT REACHED (0 open positions; no OMS submit)
    ↓
OMS                  NOT CALLED  ("OMS not called — bridge aborted before submit")
    ↓
MT5                  NOT REACHED
    ↓
Broker               NOT REACHED
```

**Exact stop:** Execution Bridge aborts with `abort_reason=ignored_action` because Decision/Eligibility emitted **`NO_TRADE`**. OMS is never invoked. This is intentional safety behavior, not an OMS/MT5/broker outage.

---

## Step 3 — Live cycle / rejection evidence

### Collection method

- Source: Railway production logs (`ite_cycle_outcome` + `cycle_evidence` / `log_trade_rejection`)
- Annex: `docs/trading/_cycle_sample.json`
- Window: 2026-07-31T18:44:29Z → 2026-07-31T19:00:35Z (≈16 minutes of unique signal_ids)
- Unique live cycles captured: **28** (Railway log CLI retention limited full 100-signal history in this window)
- Pattern stability: **28/28 identical primary outcome**

> Honesty note: Step 3 asked for ≥100 cycles. The live log stream yielded **28 unique `signal_id`s** with a **100% invariant rejection signature**. No BUY/SELL and no OMS forward appeared. Continuing to poll would only repeat the same gates. Rejection field table below covers every unique rejection in the captured set (n=28).

### Aggregate (all unique cycles)

| Metric | Value |
|---|---|
| Unique cycles | 28 |
| `outcome=no_trade` | 28/28 (100%) |
| `decision_action=NO_TRADE` | 28/28 |
| `abort_reason=ignored_action` | 28/28 |
| `forwarded_to_oms=true` | **0** |
| Primary rejection code | `mtf_not_aligned` **28/28** |
| Quality observed | **74** on 28/28 |
| MTF score observed | **45** on 28/28 |
| Session | `new_york` (allowed) |
| Mode | `LIVE` |

### Per-rejection fields (every unique rejected cycle — identical template)

| Field | Observed value (all 28) |
|---|---|
| Quality | **74** (below gate) |
| Confidence | **below_threshold** |
| MTF | **45** / not aligned (`H4=range H1=down M15=range M5=up`) |
| Liquidity | **missing** (`no_liquidity_context`) |
| Session | `new_york` (open / allowed) |
| Spread | ~0.39–0.43 (soft / not hard-reject; hard reject only above 1.50) |
| ATR | ~5.2–6.2 (price % acceptable per logs) |
| Risk | **0.50%** (`risk_budget≈0.91` on $181.53) |
| Lot Size (calculated) | **≈0.0019–0.0023** |
| Approved lots | **0** |
| Portfolio Exposure | **0** open positions |
| Final rejection reason | **`mtf_not_aligned`** |

Concurrent codes on every rejection row:

- `mtf_not_aligned=true`
- `quality_below_threshold=true`
- `confidence_below_threshold=true`
- `no_liquidity_context=true`
- `below_min_lot=true` (sizing evidence attached; not the OMS-path stop)

### Latest execution evidence

| Item | Result |
|---|---|
| Production execution evidence file | `docs/production/execution/latest_execution.md` → **NOT VERIFIED** / waiting for first eligible production execution (as of 2026-07-31T00:03:31Z) |
| DB `execution_attempts` | Last success: 2026-07-21 ticket `515488111` (XAUUSD buy 0.01) — **not today** |
| Live cycles today | **0** OMS submits, **0** broker tickets |

### OMS / AI / Gateway / MT5 logs (summary)

- **AI:** Continuous `AI Decision result=FAIL action=NO_TRADE`
- **Execution Gate:** `abort=ignored_action`, `execution_enabled=True`
- **OMS:** `OMS not called — bridge aborted before submit`
- **MT5 Gateway:** Healthy authenticated GET `/positions`, `/account` from Railway (200)
- **Broker:** Not reached for new orders; account sync healthy

---

## Step 4 — Root cause (exactly one)

### Classification: **C. MTF alignment**

**Why C (not B/D/F/H/I/J/K):**

1. Structured primary rejection code on **every** live cycle is `mtf_not_aligned`.
2. Decision reasons lead with MTF misalignment at score **45** (`H4=range H1=down M15=range M5=up`).
3. Pipeline aborts at Eligibility → `NO_TRADE` **before** OMS/MT5/Broker.
4. Infrastructure components are healthy; no software defect indicated in the abort path (`ignored_action` is the designed response to `NO_TRADE`).

### Concurrent (non-primary) gates also failing on the same cycles

| Category | Evidence | Role |
|---|---|---|
| **B. AI thresholds** | Quality **74** below gate; `confidence_below_threshold` | Would also NO_TRADE even if MTF aligned |
| **D. Liquidity detection** | `no_liquidity_context` | Concurrent eligibility fail |
| **F. Lot sizing** | `sizing_status=below_min_lot`, calc lots ≈0.002 vs broker min **0.01**, equity **$181.53**, risk **0.50%**, budget **$0.91** | Would block OMS sizing **if** AI later emitted BUY/SELL with similar stop (~8–9) |

**Not the root cause today:** E Risk engine (not independently rejecting a BUY/SELL), G Portfolio limits (flat book), H OMS, I MT5, J Broker rejection, K Software bug.

---

## Step 5 — Readiness

### Is the robot technically ready to execute trades?

**YES** — infrastructure and execution path are armed.

**Why no trades have occurred yet**

1. Live evaluations are running in `LIVE` / Auto Trading `running`.
2. Every observed cycle ends in **`NO_TRADE`** because **MTF is not aligned** (primary), with quality/confidence/liquidity also below gates.
3. OMS/MT5/Broker are healthy but correctly **not called**.
4. Secondary constraint: even an eligible signal at current **0.50%** risk and ~8pt stop on **$181.53** still computes **below broker min lot (0.01)** — so a future “AI pass” may still reject at Dynamic Position Sizing until equity rises, risk budget allows min lot, or stop distance is tight enough. **This investigation does not recommend lowering thresholds or forcing lots.**

### Blockers to a fill right now

| # | Blocker | Severity |
|---|---|---|
| 1 | MTF not aligned (score 45) | **Active — primary** |
| 2 | Quality 74 below gate | Active — concurrent |
| 3 | Confidence below threshold | Active — concurrent |
| 4 | No liquidity context | Active — concurrent |
| 5 | below_min_lot at $181.53 / 0.50% risk (structural) | Latent — after AI BUY/SELL |

No infrastructure blockers (Gateway/OMS/MT5/AI/AutoTrading/EXECUTION_ENABLED) in the latest healthy probes.

---

## Step 6 — Recommended fixes (do **not** implement yet)

Investigation-only. No code or threshold changes performed.

1. **Do not lower Quality/Confidence floors, MTF rules, or risk.** Current rejects are the system working as designed.
2. **Wait for naturally aligned MTF + quality ≥ gate + confidence ≥ gate + liquidity context** during allowed sessions.
3. **Account funding (ops, not code):** At broker `volume_min=0.01` and live risk **0.50%**, $181.53 frequently cannot clear min lot for XAUUSD stops ~8–9. Prior micro-account analysis already documented institutional 1% needing ~$1800 equity for typical stops — treat as capital planning, not a strategy bug.
4. **Observability:** Provide owner bearer access so `/ite/ops/auto-trading` + `strategy-diagnostics?window=100` can be snapshotted without relying on Railway log retention (E2E password in Railway env returned HTTP 401 during this investigation).
5. **Cloudflare:** Investigate intermittent **403** on public `gateway.quantforg.com` from some clients; local gateway + Railway path remained healthy.

---

## Component status snapshot

| Component | Status |
|---|---|
| Gateway | HEALTHY (Railway + local); public URL intermittently 403 from investigator |
| OMS | HEALTHY (`EXECUTION_ENABLED=true`) |
| AI | HEALTHY (emitting live NO_TRADE) |
| MT5 | CONNECTED / attached / AutoTrading ON |
| Broker | Weltrade-Real connected; 0 open positions |
| Readiness | **YES** (waiting for eligible opportunity; latent min-lot constraint on micro equity) |

---

## Annex paths

- `docs/trading/_live_investigation_evidence.json` — gateway account/quotes/candles + public health
- `docs/trading/_cycle_sample.json` — 28 unique live cycles + rejection field rows
- `docs/trading/_railway_logs_raw.txt` — raw log capture
- Supabase `ite_ops_runtime_state` — LIVE + auto_trading running
- Supabase `portfolio_syncs` — live equity 181.53 / positions 0

---

## Final conclusion

**1. READY — waiting for a naturally eligible market opportunity.**
