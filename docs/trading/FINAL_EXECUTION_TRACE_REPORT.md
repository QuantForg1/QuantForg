# Final Execution Trace Report

**Investigation type:** Observe-only — no code, threshold, risk, or strategy changes  
**Generated at:** 2026-07-31T19:55:00Z  
**Production SHA:** `76344ca12b35763be02d682de4894d0dcae1e9b5` (`ite-v2.2.0`)  
**Related:** [`AI_PIPELINE_SYNCHRONIZATION_REPORT.md`](./AI_PIPELINE_SYNCHRONIZATION_REPORT.md)

---

## Selected live cycle (MTF PASS · Quality ≥ 80 · Confidence ≥ 80)

| Field | Value |
|---|---|
| Timestamp | `2026-07-31T19:51:07.526665Z` |
| Signal ID | `182769f4-7e78-46fe-8790-4731dee4ce55` |
| Mode | `LIVE` · session `new_york` |
| Outcome | `no_trade` |
| Decision action | `NO_TRADE` |
| Abort | `ignored_action` |
| Forwarded to OMS | **False** |
| Trace evidence | `docs/trading/_final_trace_evidence.json` |

### Institutional metrics on this cycle (already cleared)

| Metric | Current | Required | Result |
|---|---|---|---|
| MTF v2 | aligned · score **100** · bias=down · H1+M15 lock | aligned | **PASS** |
| Quality (ITE) | **89** (`tradable`) | ≥ **80** | **PASS** |
| Confidence (confluence / lifecycle) | **92** (`detail='action=NO_TRADE conf=92'`) | ≥ **80** | **PASS** |

---

## Complete gate trail (this cycle)

Pipeline order as executed in production (scalping mode):

```text
AI Scalping Score + Quality Gates
    ↓
Confluence (ITE) + Executable Direction
    ↓
Eligibility
    ↓
Risk Engine
    ↓
Dynamic Position Sizing
    ↓
Portfolio Risk Engine
    ↓
OMS → MT5 → Broker
```

### 1. AI Decision — Market / ITE confluence inputs

| Gate | PASS / FAIL | Exact reason / values |
|---|---|---|
| Market data live | **PASS** | Quotes/candles/account feeding cycle |
| MTF v2 | **PASS** | `MTF v2 ranging: aligned bias=down (H4=range context H1=down M15=down M5=up score=100)` |
| M15 semantics | **PASS** | `M15 semantics=PULLBACK_WITHIN_TREND` · H1+M15 lock |
| Structure (BOS/CHOCH) | **PASS** (present) | `bos=12 choch=13` · `Latest BOS trend=down` |
| Liquidity v2 (ITE) | **PASS** | `Liquidity v2 sources=validated_order_block,mitigation,displacement,respected_fvg,imbalance_reaction` |
| Order blocks | **PASS** | `Validated/active order blocks=1` |
| FVGs | **PASS** | `Respected/active FVGs (imbalance)=4` |
| ITE Trade Quality | **PASS** | **89** ≥ 80 · band `tradable` · confidence quality slot passthrough (dedup) |
| ITE Confluence confidence | **PASS** | **92** ≥ 80 |
| Session | **PASS** | `new_york` open · 24/7 desk |
| News | **PASS** | protection disabled / not blocking |
| Spread (ITE soft) | **PASS** (soft only) | `0.434` elevated · soft score 96 · hard reject only above **1.50** |
| ATR note (ITE) | informational | `ATR 0.13% of price acceptable` (ITE narrative) |

### 2. AI Scalping Quality Gates — **FAIL (blocking)**

In scalping mode, `institutional_decision_pipeline` runs `score_ai_scalping_setup` → `evaluate_quality_gates`.  
If `ai_score.reject is True`, `resolve_executable_direction` forces:

> `AI quality gates rejected — NO_TRADE`

That exact string is present on this cycle.

**Proven failing check (reproduced from live ATR + mid):**

| Field | Value |
|---|---|
| **Gate name** | AI Scalping Quality Gates → `valid_volatility` |
| **Condition** | When volatility band == `low`, require `atr_pct >= atr_low_pct / 2` |
| **Current value** | `atr_pct ≈ 0.1268%` (ATR `5.1357` / mid ≈ `4050.17`) · band = **`low`** |
| **Required value** | `atr_pct >= 0.20%` (`atr_low_pct=0.40` / 2) while band is `low` |
| **Code** | `app/domain/institutional_trading/ai_scalping/quality_gates.py` (`Volatility too compressed ATR%=…`) |
| **Config** | `require_valid_volatility=True` · `atr_low_pct=0.40` (`ai_scalping/config.py`) |

Reproduction (read-only):

```text
band=low  atr_pct≈0.1268  adaptive_q=88  adaptive_c=88
ITE quality 89 ≥ 88  → adaptive quality would PASS
confidence 92 ≥ 88   → adaptive confidence would PASS
BUT atr_pct 0.1268 < 0.20 → valid_volatility FAIL
```

**Collapsed log reason (what Eligibility sees):**  
`AI quality gates rejected — NO_TRADE`  
(detail list of REJECT lines is not always expanded in Railway cycle reasons; volatility fail is independently proven from live ATR% + gate formula.)

Other AI scalping checks on this market state (supporting context — not needed once volatility fails):

| Check | Likely | Notes |
|---|---|---|
| Adaptive quality / confidence | would PASS | 89/92 vs floors 88/88 (low-vol band) |
| Momentum / structure floors | likely PASS | alignment score 100 ≥ 65/70 |
| Liquidity event score | likely PASS | Liq v2 quality factor feeds ≥60 path when OB/FVG present |
| Spread hard reject | PASS | 0.434 ≪ max reject |
| Clear BUY/SELL direction | unknown in logs | mixed bos/choch counts could also balance; not required to establish the volatility fail |

### 3. Executable Direction

| Gate | PASS / FAIL | Exact reason |
|---|---|---|
| `resolve_executable_direction` (scalping · `ai_reject=True`) | **FAIL** | `AI quality gates rejected — NO_TRADE` · direction forced to **NONE** · source=`none` |

Code: `app/domain/institutional_trading/executable_direction.py` lines 74–78.

### 4. Eligibility

| Gate | PASS / FAIL | Exact reason |
|---|---|---|
| Eligibility overall | **FAIL** | `Eligibility failed — NO_TRADE` |
| `validated_direction` / confluence side | **FAIL** | rejection includes `AI quality gates rejected — NO_TRADE` / `no_validated_direction` path |
| Current | `eligible=False` · `direction=NONE` · `action=NO_TRADE` | |
| Required for continue | `eligible=True` with BUY or SELL | |

Because executable direction is NONE, pipeline **returns early** from `institutional_decision_pipeline` **before** RiskEngine.evaluate (see early return when `side not in {buy,sell}`).

### 5. Risk Engine

| Gate | PASS / FAIL | Exact reason |
|---|---|---|
| Risk Engine | **NOT REACHED** | No BUY/SELL side to size; decision already `NO_TRADE` |
| Shadow/primary risk_score | `100` on primary snapshot | consistent with hard reject path |

### 6. Dynamic Position Sizing

| Gate | PASS / FAIL | Exact reason |
|---|---|---|
| Dynamic sizing (OMS path) | **NOT REACHED** | Short-circuited by AI reject / no side |
| Diagnostic sizing attached to cycle evidence | **would FAIL if reached** | see latent values below |

**Latent sizing snapshot (evidence-only, not the active stop):**

| Field | Current | Required |
|---|---|---|
| Gate | `below_min_lot` (latent) | calculated ≥ broker min |
| Calculated lot | ≈ **0.00236** | ≥ **0.01** |
| Risk % | **0.50** | (configured scalping risk) |
| Risk budget | **$0.91** | — |
| Stop distance | **7.7036** | — |
| Balance | **181.53** | — |

### 7. Portfolio Risk Engine

| Gate | PASS / FAIL | Exact reason |
|---|---|---|
| Portfolio Risk Engine | **NOT REACHED** | No approved side / lots |

### 8. OMS

| Gate | PASS / FAIL | Exact reason |
|---|---|---|
| OMS submit | **NOT REACHED** | Bridge: `abort_reason=ignored_action` · `OMS not called — bridge aborted before submit` |

### 9. MT5 / Broker

| Gate | PASS / FAIL | Exact reason |
|---|---|---|
| MT5 order_send | **NOT REACHED** | No OMS call |
| Broker fill | **NOT REACHED** | No MT5 order |

Infrastructure remains healthy (gateway/OMS/MT5 connected) but unused this cycle.

---

## Which component still returns NO_TRADE?

**AI Scalping Quality Gates** (`evaluate_quality_gates`), specifically check **`valid_volatility`**.

Flow:

1. Live ATR% ≈ **0.13%** → volatility band **`low`**.  
2. Gate requires ATR% ≥ **0.20%** in the low band (`atr_low_pct/2`).  
3. Gate fails → `ai_score.reject=True`.  
4. `resolve_executable_direction` emits **`AI quality gates rejected — NO_TRADE`**.  
5. Eligibility fails · Risk / Sizing / PRE / OMS never run.

ITE MTF / Quality 80 / Confidence 80 are **not** the remaining blocker on this cycle.

---

## Conclusion

**2. BLOCKED BY AI Scalping Quality Gate: valid_volatility (Volatility too compressed — ATR% 0.13 < required 0.20 in low band)**
