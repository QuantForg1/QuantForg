# QuantForg Phase 4 — LIVE Robot Verification & Continuous Monitoring

**As of:** 2026-11-03T20:27–20:35Z (authenticated production probes)  
**Deployed commit:** `648e1d7c8c24a723d5416373c5edf3ab95edf6c9` (Railway deployment `8f8c9b6f-…`)  
**SOE version (live):** `soe-v1.3.0` (not v1.2.0)  
**Auth:** Owner JWT via secure Admin magic-link exchange — tokens not logged.  
**Unauthenticated `/robot-health-monitor` → HTTP 401** is expected gate behavior, not a robot failure.

---

## 1. Robot operational status

| Check | Evidence |
|---|---|
| Process / ITE | LIVE, `auto_trading` **Enabled**, `ops_mode=LIVE`, cycles running |
| Last cycle | `2026-11-03T20:27:52Z` (process-local; ~5s before probe) |
| Market data | Fresh (`last_quote_age_seconds=0`, `market_data_fresh=true`) |
| Gateway / MT5 | Connected — gateway health OK, MT5 attached Weltrade-Real, magic sync OK |
| Scanner / workers | Multi-asset scan active; universe GOLD_ONLY → `XAUUSD`; scanner + ITE loop alive |
| SOE last decision | **NO_TRADE** — “No selectable strategy after filters, influence, and conflict resolution” |
| OMS / execution | `EXECUTION_ENABLED=true`, OMS HEALTHY, orders authorized; **1 open position** blocks new handoffs (`max_open_trades=1`) |
| Kill / force / override | Emergency stop off; `FORCE_FIRST_TRADE=false`; `ALLOW_RISK_LOCK_OVERRIDE=false` |
| Open broker position | Ticket `682130079` XAUUSD buy 0.01, magic `260720`, comment `m1:mom-buy-3922.053`, SL/TP set |

**Verdict:** Robot is **operationally LIVE** (gateway, MT5, market data, scanner, SOE evaluations, OMS path). It is **not** currently selecting five-pack OMS winners; last SOE decision is NO_TRADE while an M1 position is open.

---

## 2. Five strategies (individual)

All five are **registered** `live_executable`, **enabled for analysis/OMS selection**, and **actively evaluated** every cycle. None are “operational as trade generators” in this window — all `ACTIVE_NO_VALID_SETUP`, **0 accepted / 31 rejected** (process-local since last restart), **0 matched closed trades** in StrategyStatsBook.

| strategy_id | Registered | Enabled (OMS-eligible) | Last eval | Market data | Evals | Signals gen | Rejected (latest reason summary) | OMS eligibility now | Matched closed | Net perf |
|---|---|---|---|---|---|---|---|---|---|---|
| smc_scalping | Yes | Yes | 20:27:52Z | Yes | 31 | 0 | ATR% 0.0676 &lt; 0.08; Q68&lt;75; no edge/TP room | No (rejected) | 0 | insufficient |
| trend_continuation | Yes | Yes | 20:27:52Z | Yes | 31 | 0 | Same ATR/Q/edge gates | No | 0 | insufficient |
| breakout_scalping | Yes | Yes | 20:27:52Z | Yes | 31 | 0 | + ATR band not high/normal | No | 0 | insufficient |
| range_mean_reversion | Yes | Yes | 20:27:52Z | Yes | 31 | 0 | + regime `strong_trend` ≠ range/compression | No | 0 | insufficient |
| momentum_scalping | Yes | Yes | 20:27:52Z | Yes | 31 | 0 | ATR/Q/edge (quality scored 75 but base gates fail) | No | 0 | insufficient |

Process-local telemetry: `rejected_signals=31`, `executed_signals=0`, `high_quality_signals=0`, `risk_block_count=25`.  
**Do not treat registry membership as operational profitability.**

---

## 3. Authenticated health verification

| Endpoint | HTTP | Notes |
|---|---|---|
| `/api/v1/ite/ops/robot-health-monitor` | **200** | Full strategy + robot + M1 + risk defaults |
| `/api/v1/ite/ops/auto-trading` | **200** | LIVE enabled; orchestrator + SOE rejections |
| `/api/v1/ite/ops/strategy-orchestration-monitor` | **200** | soe-v1.3.0 |
| `/api/v1/ite/ops/strategy-performance-telemetry` | **200** | Process-local; 0 executed |
| `/api/v1/ite/ops/services-health` | **200** | gateway/OMS/MT5/AI healthy; commit `648e1d7c…` |
| `/api/v1/ite/ops/production-reliability` | **200** | |
| `/api/v1/ite/ops/rc1-production-validation` | **200** | Validation mode **off** (paper dashboard idle) |
| `/api/v1/ite/ops/noc-command-center` | **200** | |
| `/api/v1/portfolio`, `/api/v1/positions` | **200** | 1 open M1 position |
| Unauthenticated robot-health | **401** | Auth gate OK |

Artifacts: `docs/production/reports/phase4/*.json`

---

## 4. Exact owner policy verification

### A. Persisted runtime (`trading_runtime_config` v12, worker_applied=12)

| Owner YAML field | Expected | Live persisted / enforced | Match? |
|---|---|---|---|
| target / absolute risk per trade | 20% / 20% | `max_planned_risk_pct=20` | **YES** |
| daily_loss_halt | 48% | `daily_loss_pct=48` | **YES** |
| weekly_loss_halt | 0% (off) | `weekly_loss_pct=0` | **YES** |
| overall_drawdown_halt | 0% (off) | `max_drawdown_pct=0` | **YES** |
| max_aggregate_open_risk | 30% | `30` | **YES** |
| max_concurrent_positions | **1** | Document has **5**; `active_max_open_positions()` **clamps to 1** | **Enforced YES** / document noisy |
| minimum_net_reward_risk | **1.5** | Persisted `min_reward_risk=0.20` + `experimental_promoted=true` → **active floor 0.20** | **NO — MISMATCH** |
| preferred_reward_risk | 2.0 | Code `PREFERRED_REWARD_RISK=2.00` (scoring) | YES (code) |
| minimum_trade_quality | 75 | 75 | **YES** |
| max_lot | 0.01 | 0.01 | **YES** |
| atr_stop_multiplier | 1.0 | `stop_atr_multiplier=1.00` | **YES** |
| mandatory_stop_loss | true | `protective_stop_required=true` | **YES** |
| grid / martingale / averaging | false | Code + live diagnostics forbid | **YES** |
| max_spread (owner hard) | 1.00 | Runtime `max_spread=1.00` | **YES** |

**Open M1 position geometry (evidence RR &lt; 1.5 is allowed under promoted 0.20):**  
entry `3922.017`, SL `3920.023` (~1.994 risk), TP `3924.083` (~2.066 reward) → raw RR ≈ **1.04** (&gt;0.20, **&lt;1.50**).

### B. Control-plane AutoTradePolicy (ops display)

- `risk_per_trade_pct=1.0`, `max_spread=2.00` — **diverges** from owner YAML / runtime document. Entry hard guards still use owner/runtime clamps (`≤20%`, spread `≤1.00`). Not silently rewritten.

### C. M1 flags (Railway env — owner-controlled, not auto-changed)

- `QUANTFORG_M1_MICRO_SCALPING=true`
- `QUANTFORG_M1_MICRO_LIVE_SUBMIT=true` (**ON**)
- Robot-health recommendation: confirm Admin Off unless new evidence supports LIVE (flags not flipped by this verification).

---

## 5. Live signals & rejection statistics

**SOE (process-local since restart):** 31 cycles; decision **NO_TRADE**; all five pack candidates rejected each cycle.  
**Dominant reject cluster:** dead-tape ATR% &lt; 0.08; owner min quality 75 (observed AI quality ~68); no directional edge / TP room; regime gates where applicable.  
**ITE:** Opportunities selected for XAUUSD but **blocked by portfolio** (1/1 open).  
**Five-pack OMS winners this window:** none.

---

## 6. Matched broker performance (MT5, 30d, magic 260720, XAUUSD)

Method: join deals by `position_id`; classify via **entry** comment (`m1:*` vs `ite:*`). Exit comments are `[sl]`/`[tp]` only — five-pack `strategy_id` **not** present on closed broker comments → **no five-pack profitability claim**.

| Book | Closed positions | Net P&amp;L after costs | Profit factor | Expectancy | Win rate | Avg win | Avg loss | Max DD (closed curve) |
|---|---|---|---|---|---|---|---|---|
| **M1** (`m1:*` entries) | 32 | **-23.18** | 0.52 | -0.72 | 34.4% (11W/21L) | +2.29 | -2.30 | 26.22 |
| **ITE** (`ite:*` entries) | 30 | **+18.14** | 1.42 | +0.60 | 46.7% (14W/16L) | +4.35 | -2.68 | 12.12 |
| Five-pack by `strategy_id` | 0 matched | — | — | — | — | — | — | insufficient |

Account snapshot at probe: balance **15.31**, equity ~**14.5**, 1 open M1 buy (floating loss).  
**M1 separately is not profitable** on this matched sample while LIVE submit remains ON.

---

## 7. Problems found and fixed

| Item | Severity | Action |
|---|---|---|
| Unauthenticated ops → 401 | None (gate) | Confirmed OK |
| Five strategies rejecting (ATR/Q/regime) | Operational | No code defect — gates working; not loosened |
| `min_reward_risk` live **0.20** (promoted) vs owner brief **1.50** | **Policy mismatch** | **Reported only** — not silently changed |
| Control-plane policy display 1% / spread 2.00 vs runtime 20% / 1.00 | Ops-layer drift | Reported; hard clamps still bind |
| M1 LIVE submit ON + matched M1 expectancy negative | Owner flag risk | Reported; **not** flipped |
| Five-pack broker attribution absent on exits | Monitoring limitation | Position_id join used for M1/ITE; no trading-core change |
| Code defects requiring deploy | — | **None verified that require a production code deploy** |

---

## 8. Remaining blockers / owner decisions

1. **Confirm whether promoted `min_reward_risk=0.20` is still intended** vs restore YAML **1.50** (and clear `experimental_promoted`).
2. **Confirm M1 LIVE submit** should stay ON given matched M1 net **-23.18 / PF 0.52**.
3. Five-pack has **insufficient closed attributed sample** for profitability claims.
4. Dead-tape ATR environment → expect continued NO_TRADE from five-pack until volatility/quality clears floors.
5. Open position occupies the single concurrent slot — no additional five-pack entries until flat.

---

## 9. Deployment evidence

- **No new code deploy** in Phase 4 (verification-only; no verified code defect requiring ship).
- Production already on Phase 3 merge **`648e1d7c`** / Railway **`8f8c9b6f`** / services-health confirms same commit.
- Vercel dual deploy remained READY from Phase 3 (not re-touched).

---

## Continuous monitoring mechanism

**Primary (authenticated):** `GET /api/v1/ite/ops/robot-health-monitor`  
Alerts to watch:

- `robot.market_data_fresh == false` or rising `last_quote_age_seconds`
- `robot.last_error != null` or stalled `last_cycle_at`
- Strategy `operational_status` in `{DISABLED, DATA_UNAVAILABLE, ERROR}` or long `ACTIVE_NO_VALID_SETUP` with zero scans
- `m1.m1_live_submit == true` while M1 matched expectancy remains negative
- `performance.deteriorating_strategy_ids` non-empty
- Services-health: gateway/MT5/OMS not HEALTHY/CONNECTED
- Policy: re-read `trading_runtime_config` for `min_reward_risk` / `experimental_promoted` drift vs owner YAML

**Supporting:** `/ite/ops/auto-trading`, `/ite/ops/services-health`, `/ite/ops/strategy-orchestration-monitor`, gateway `/history/deals` position_id attribution (see `m1_position_attribution.json`).

**Local evidence pack:** `docs/production/reports/phase4/`

---

*Disclaimer: Historical / matched broker data does not guarantee future profitability. Registry membership ≠ operational edge.*
