# QUANTFORG — Reversal Intelligence + M1 Strategy Integration

**Date:** 2026-11-06  
**Baseline:** PR #178 / commit `c46ba027` (capital protection mission)  
**Instrument:** XAUUSD  
**Scope:** Audit + shadow-safe intelligence improvements. **No LIVE reversal activation. No M1 LIVE submit activation.**

---

## 1. Existing reversal implementation and gaps

### What already existed

| Layer | Status | Notes |
| --- | --- | --- |
| `PositionManagementConfig.shadow_reversal_exits_enabled` | **True** (default) | Observe / log / durable book only |
| `PositionManagementConfig.live_reversal_exits_enabled` | **False** (default) | Must stay False until owner approval |
| `propose_reversal_exit` (`management/exit_context.py`) | Present | Distinguishes retracement vs confirmed structure |
| `shadow_exit_book` | Present | Ring buffer + durable JSON under data dir |
| ITE manage-cycle hook | Present | Records shadow proposals; feeds planner **only** if LIVE flag on |
| Close-then-reverse sequence | **Missing before this PR** | No gated broker-confirm → opposite-entry evaluator |

### Gaps found (pre-fix)

1. **`_shadow_reversal_kwargs` was not side-aware.**  
   Any high BOS/CHOCH *score* (`bos >= 70` / `choch >= 70`) was treated as “against the position,” regardless of whether the structure event continued the open side or opposed it. That invents false bearish pressure on a BUY (and the reverse).
2. **No explicit classification** of temporary M1 pullback vs confirmed M5/M15 structure vs HTF trend reversal vs false noise.
3. **No close-then-reverse gate.** There was no pure evaluator encoding: never open opposite before broker-confirmed close; never treat a close request as confirmation; never reverse to recover a loss.
4. **`data_age_seconds` was always `None`**, so the stale-data branch of `propose_reversal_exit` never fired from ITE.

### What this change fixed (shadow only)

- Side-aware opposition from mapped BOS/CHOCH events via `structure_event_side` / `structure_tfs_for_side`.
- Explainable `classification` on `ReversalExitProposal`.
- Pure `evaluate_close_then_reverse` with hard rejects; ITE logs stage, never submits opposite (`live_reverse_entry_enabled=False`).
- Best-effort `data_age_seconds` from snapshot `as_of` / `timestamp`.

**LIVE behavior unchanged:** `live_reversal_exits_enabled` remains False; planner is not fed structure/trend exit booleans in production.

---

## 2. Existing M1 strategies and actual status

### Identity

| ID | Module | Role |
| --- | --- | --- |
| `m1_micro` | `app/domain/institutional_trading/m1_micro/` | Cost-checked M1 setups |

### Setups in `m1_micro/signals.py` (candidate generation)

1. `momentum_continuation` (BUY/SELL with HTF bias agreement)  
2. `pullback_continuation` (BUY pullback in up bias)  
3. `range_breakout` (BUY/SELL)  
4. `confirmed_micro_reversal` (liquidity sweep + close confirmation; still requires HTF bias)

Volatility screen rejects quiet markets (`atr <= 3×spread`) and spikes (`latest > 4×atr`).

### Activation flags (why LIVE submit is disabled)

| Flag | Default | Effect |
| --- | --- | --- |
| `QUANTFORG_M1_MICRO_SCALPING` | unset / false | Module disabled → `action=disabled` |
| `QUANTFORG_M1_MICRO_LIVE_SUBMIT` | unset / false | Even if module on, no LIVE OMS submit |
| Runtime policy overlay `m1_micro_enabled` / `m1_live_submit` | can force **off** | Cannot force **on** when env flags are off |

`live_eligibility.py` lists `m1_micro` as **`ops_gated`**, `live_oms=False`.

### Shadow / candidate availability

- Unit path (`evaluate_m1`) can propose buys/sells when the module flag is on — **not** the same as LIVE.
- `unified_decision.resolve_unified` already arbitrates primary vs M1: direction conflict → wait; same direction → single owner; never two orders; never flip.
- M1 without a protective stop is ignored for submit.
- **Do not treat codebase presence as LIVE readiness.** Historical/shadow expectancy for M1 on Weltrade XAUUSD was **not** proven in this mission from broker candles (see §6).

### Interaction with other strategies

Primary ITE stack (confluence / registered scalping strategies) remains the executable owner when it has a same-direction entry. M1 is confirmation or fallback owner only when primary did not take the entry — and only if LIVE submit flags are on (they are not).

---

## 3. Reversal engine design

### Classification ladder (explainable)

| Classification | Meaning | Exit proposal |
| --- | --- | --- |
| `temporary_m1_pullback` | LTF noise / retracement | No |
| `false_reversal_noise` | LTF BOS/CHOCH without HTF agreement | No |
| `genuine_momentum_change` | AI confidence fade + momentum deterioration | Soft (trend_reversed via AI fade) |
| `confirmed_structure_reversal` | Against-side BOS/CHOCH **and** HTF agrees | Yes (shadow) |
| `htf_trend_reversal` | Against-side CHOCH **and** HTF agrees | Yes (shadow) |
| `none` | Stale, spread defer, or no evidence | No |

### Evidence used

- Closed-structure event sides (BOS/CHOCH), not raw presence scores  
- M5/M15 membership in against-side TFs  
- Directional decision edge vs margin for HTF agreement  
- Momentum / AI confidence fade  
- Spread emergency deferral to existing PME path  
- Stale snapshot age when available  

**Rule:** one M1 candle color change never closes a position.

---

## 4. M1 integration design

### Intended cooperation (already largely encoded)

1. Collect primary + M1 normalized signals.  
2. Conflict BUY vs SELL → **wait** (no hedge, no flip).  
3. Same direction → one owner; no confidence inflation.  
4. M1 supplies LTF timing; HTF bias remains a hard filter inside `detect_setup`.  
5. All approved entries still pass Trade Quality (≥70), Risk Engine, OMS, mandatory broker SL.

### What is **not** done in this change

- Enabling `QUANTFORG_M1_MICRO_SCALPING` or `QUANTFORG_M1_MICRO_LIVE_SUBMIT` in production.  
- Lowering quality floor, edge margin, or inventing M1 edge without OOS evidence.  
- Duplicate strategy implementations.

### Suitability verdict (audit)

| Setup | Complete in code | LIVE suitable now? |
| --- | --- | --- |
| momentum_continuation | Yes | **No** — needs shadow telemetry + costed expectancy |
| pullback_continuation | Yes (BUY path) | **No** |
| range_breakout | Yes | **No** — spread-sensitive on gold |
| confirmed_micro_reversal | Yes | **No** — highest false-positive risk without HTF+M5 confirm in LIVE path |

---

## 5. Strategy coordination and conflict resolution

`unified_decision.resolve_unified` is the single entry arbitrator:

- Opposite sides → `direction_conflict` / wait  
- Same side + primary executable → primary owns; M1 confirmation only  
- Same side + primary not executable → M1 may own once  
- No actionable signal → wait  
- Does **not** inflate Trade Quality or Opportunity scores  

Ensemble / orchestrator monitoring may list `m1_micro` as advisory; OMS still receives **one** approved decision through the existing pipeline.

---

## 6. Historical / shadow validation results

### Available

- Broker-confirmed closed-trade capital-protection analysis (mission → PR #178).  
- Unit/regression coverage for classification and close-then-reverse gates (this PR).

### Not available / not invented

- Chronological candle backtest of the new side-aware shadow kwargs on Weltrade XAUUSD.  
- Measured reversal success rate, false-reversal rate, or reversal slippage from production shadow book (book may be empty or unexported on Railway until cycles accumulate).  
- M1 LIVE or shadow expectancy after costs on the current account.

**Comparisons A–D requested by the owner are therefore incomplete pending shadow accumulation:**

| Mode | Status |
| --- | --- |
| A. Existing strategy behavior | Baseline = PR #178 capital report |
| B. Reversal engine shadow | **Instrumented now**; metrics pending live cycles |
| C. M1 strategies shadow | Code path exists; flags off in production |
| D. Combined shadow | `resolve_unified` covered by unit tests; LIVE combined off |

---

## 7. Tests and failures

### Added

`tests/unit/test_reversal_intelligence.py` — genuine bull/bear, M1 pullback, false M1, conflicting TF, stale data, spread spike, unconfirmed/failed close, loss-recovery forbid, cooldown, side-aware BOS same-side, opposing CHOCH.

### Ran (local)

```
tests/unit/test_reversal_intelligence.py
tests/unit/test_pme_broker_confirm_net_be.py
tests/unit/test_m1_micro_scalping.py
tests/unit/test_unified_decision.py
→ 67 passed
```

Ruff clean on touched modules; Black applied.

### Not claimed

Full `pytest -m trading_core` suite runtime on this agent turn; CI on the PR/commit is the authoritative gate.

---

## 8. Owner policy confirmation (unchanged)

| Policy | Value | Touched? |
| --- | --- | --- |
| Risk per trade | 20% | **No** |
| Absolute risk ceiling | 20% | **No** |
| Daily loss halt | 48% | **No** |
| Max lot | 0.01 | **No** |
| Min trade quality | 70 | **No** |
| Min net RR | 0.20 | **No** |
| Preferred RR | 0.50 | **No** |
| Max concurrent | 1 | **No** |
| Max aggregate open risk | 30% | **No** |
| Mandatory broker-confirmed SL | Required | **No** |
| Grid / martingale / averaging | Disabled | **No** |
| LIVE reversal exits | Off | **Kept off** |
| M1 LIVE submit | Off | **Kept off** |

---

## 9. Production activation status

| Feature | Shadow | LIVE |
| --- | --- | --- |
| Side-aware reversal observation | **On** (with existing shadow flag) | Off |
| Classification + CTR stage logging | **On** | Off |
| Feed `structure_broken` / `trend_reversed` to PME planner | Off | Requires `live_reversal_exits_enabled=True` **+ owner approval** |
| Close-then-reverse opposite entry | Evaluated in shadow; `submit_opposite` forced False | Requires new explicit owner flag after validation |
| M1 micro module | Off unless env | Off |
| M1 LIVE submit | Off | Off |

---

## 10. Remaining risks

1. Incomplete snapshot structure → opposition flags fail closed (quiet shadow); may under-report true reversals until structure_by_tf is consistently populated.  
2. Shadow book outcomes need broker P&L attachment over many cycles before LIVE close activation.  
3. Enabling LIVE close without reverse-entry still changes position lifetime — needs separate approval.  
4. Enabling M1 LIVE submit without OOS costed expectancy can raise trade frequency without edge.  
5. BUY cascade / SELL cascade protections must remain in front of any future reverse-entry path.  
6. Trading-core freeze: further LIVE PME/OMS/Risk changes need explicit product-owner approval naming the module.

---

## 11. Recommended next steps (owner approval gates)

1. **Accumulate shadow evidence** (7–14 trading days): classifications, CTR stages, broker outcomes — no LIVE flags.  
2. **Export shadow_exit_book** from Railway data dir; compute false-reversal vs confirmed rates.  
3. **Optional:** enable `QUANTFORG_M1_MICRO_SCALPING=true` in **shadow/observe** only (LIVE submit still false) for setup telemetry.  
4. **Only after evidence:** owner-named approval to set `live_reversal_exits_enabled` (close-on-confirmed-reversal only).  
5. **Separate later approval:** reverse-entry after broker-confirmed close + normal TQ/Risk/OMS/SL path + cascade guards + cooldown.  
6. **Separate later approval:** `QUANTFORG_M1_MICRO_LIVE_SUBMIT` after costed shadow expectancy clears preferred RR and does not fight primary.

---

## Change inventory (this delivery)

| Path | Change |
| --- | --- |
| `app/domain/institutional_trading/management/exit_context.py` | Classifications; LTF-without-HTF → false noise |
| `app/domain/institutional_trading/management/close_then_reverse.py` | **New** pure sequence evaluator |
| `app/application/services/institutional_ite_runtime.py` | Side-aware shadow kwargs; CTR observe logging |
| `tests/unit/test_reversal_intelligence.py` | **New** regression suite |
| This report | Audit + activation status |

**Evidence rule:** no trade, close, profit, or LIVE activation is claimed without broker/CI evidence.
