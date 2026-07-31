# Volatility Gate v2 Report

**Change type:** Adaptive institutional volatility model (evidence-calibrated)  
**Config version:** `ai-scalping-v7.2.0`  
**Generated at:** 2026-07-31T20:15:00Z  
**Related:** [`VOLATILITY_GATE_CALIBRATION_REPORT.md`](./VOLATILITY_GATE_CALIBRATION_REPORT.md)

---

## Objective

Replace the single fixed ATR compression floor (`atr_low_pct / 2` = **0.20%**) with an adaptive model that:

- Keeps institutional safety for weak setups
- Allows evidence-backed lower ATR only when **every** other institutional pillar is strong
- Records every volatility decision in AI / execution evidence
- Does **not** force trades or invent new AI signal logic

---

## Preserved (unchanged)

| System | Status |
|---|---|
| Quality floor ≥ **80** (adaptive low-vol still **88**) | Preserved |
| Confidence floor ≥ **80** (adaptive low-vol still **88**) | Preserved |
| AI safety gates (structure, liquidity, momentum, spread, PA, RR) | Preserved |
| Risk Engine | Untouched |
| Portfolio Risk Engine | Untouched |
| Dynamic Position Sizing | Untouched |
| Forced trades | None |

---

## Model (Volatility Gate v2)

| Parameter | Value | Role |
|---|---|---|
| `atr_compression_floor_pct` | **0.20%** | Standard floor (identical to v1) |
| `atr_exceptional_floor_pct` | **0.15%** | Evidence lower bound (profitable cluster 0.15–0.20) |
| `atr_hard_min_pct` | **0.15%** | Absolute dead-tape reject — never below |

### Decision rules (low band)

1. `ATR% < 0.15` → **FAIL** always (hard min), even if exceptional.  
2. `0.15 ≤ ATR% < 0.20` → **PASS only if exceptional strength**; else **FAIL** at standard 0.20.  
3. `ATR% ≥ 0.20` → **PASS** volatility (same as v1); other gates still apply.  
4. Non-`low` band → compression floor not applied (same as v1).

### Exceptional strength (ALL required)

| Pillar | Minimum |
|---|---|
| Quality | `max(80, adaptive, 88)` |
| Confidence | `max(80, adaptive, 88)` |
| Structure | ≥ 80 |
| Liquidity | ≥ 70 |
| Momentum | ≥ 70 |
| MTF alignment | ≥ 80 |
| Session stars | ≥ 4 (London / NY / overlap) |
| Spread | not reject **and** score ≥ 75 |
| Regime | `strong_trend` \| `weak_trend` \| `breakout` \| `expansion` |
| PA confluence | passed (when present) |
| Direction | clear BUY/SELL |

Weak / Tokyo / range / compression setups **cannot** use the 0.15 floor.

### Inputs used

Regime · session · liquidity · spread · AI quality · confidence · MTF alignment (plus structure / momentum / PA / direction as strength pillars).

---

## Evidence recording

Every evaluation emits `volatility_decision` on:

- `QualityGateResult.to_dict()`
- `AiScalpingScore.to_dict()` → already attached to pipeline `last_ai_score` / reject `details`

Fields include: `passed`, `atr_pct`, `applied_floor_pct`, `standard_floor_pct`, `exceptional_floor_pct`, `hard_min_pct`, `band`, `model=volatility_gate_v2`, `exceptional_eligible`, `exceptional_used`, `strength_checks`, `strength_failures`, `reason`, `legacy_would_pass`.

Cycle reasons also append the human-readable `reason` string.

---

## Before / after replay statistics

Source: M15 ATR% bucket shares from calibration (30d XAUUSD) + historical non-micro winner ATR%s.  
Unit suite: `tests/unit/test_volatility_gate_v2.py`.

### A. Market-distribution replay (low band)

| Bucket (representative ATR%) | Share of time | v1 PASS | v2 weak PASS | v2 exceptional PASS |
|---|---|---|---|---|
| &lt;0.10 (0.08) | 2.57% | No | No | No |
| 0.10–0.15 (0.125) | 27.18% | No | No | No |
| 0.15–0.20 (0.175) | 34.65% | No | **No** | **Yes** |
| 0.20–0.30 (0.25) | 29.06% | Yes | Yes | Yes |
| &gt;0.30 (0.35) | 6.53% | Yes | Yes | Yes |

| Metric | v1 | v2 (weak) | v2 (exceptional only) |
|---|---|---|---|
| Allow rate (vol gate alone) | **35.59%** | **35.59%** | **70.24%** |
| New accepts vs v1 | — | **0%** | **+34.65%** (0.15–0.20 only) |
| False-positive increase (weak) | — | **0** | n/a |

**Invariant verified:** weak setups gain **zero** new volatility accepts vs v1.

### B. Historical profitable-trade ATR replay (n=10 non-micro winners)

| Gate | Would PASS volatility |
|---|---|
| v1 fixed 0.20% | **2 / 10** |
| v2 weak path | **2 / 10** (unchanged) |
| v2 exceptional path | **10 / 10** |

Higher acceptance appears **only** where calibration evidence supports (0.15–0.20 cluster) **and** only when exceptional strength clears.

### C. Live blocker regression

| Case | ATR% | v1 | v2 exceptional |
|---|---|---|---|
| Final execution trace cycle | ≈ **0.13** | FAIL | **FAIL** (below hard min 0.15) |

Safety vs dead tape retained.

---

## Code touchpoints

| File | Change |
|---|---|
| `ai_scalping/volatility_gate_v2.py` | New adaptive model + evidence dataclass |
| `ai_scalping/quality_gates.py` | Calls v2; attaches `volatility_decision` |
| `ai_scalping/scoring.py` | Passes MTF + regime; records decision on score |
| `ai_scalping/config.py` | v7.2.0 + floor / exceptional knobs + clamps |
| `tests/unit/test_volatility_gate_v2.py` | Behavior + before/after replay |

Risk Engine, PRE, Dynamic Sizing, OMS, and MT5 paths were **not** modified.

---

## Acceptance checklist

| Criterion | Result |
|---|---|
| No increase in false positives (weak) | **PASS** (0 new weak accepts) |
| Higher acceptance only where evidence supports | **PASS** (0.15–0.20 + exceptional only) |
| Preserve institutional behavior / 80 floors | **PASS** |
| Never reduce safety (hard min 0.15; standard 0.20 for weak) | **PASS** |
| Record every volatility decision | **PASS** (`volatility_decision` on score/gates) |
| Before/after replay statistics | **PASS** (this report + unit tests) |

---

## Conclusion

**Volatility Gate v2 is calibrated:** standard floor remains **0.20%**; exceptional institutional setups may use **0.15%**; anything below **0.15%** still rejects. Weak setups cannot loosen the gate.
