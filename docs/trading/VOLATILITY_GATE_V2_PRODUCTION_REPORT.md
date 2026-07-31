# Volatility Gate v2 — Production Deployment Report

**Generated at:** 2026-07-31T20:21:00Z  
**Objective:** Deploy only approved Volatility Gate v2 to Railway Production  
**Rules honored:** No AI logic beyond approved v2 · Quality/Confidence floors ≥ 80 · Risk / PRE / Sizing / OMS / MT5 untouched · no forced trades

---

## Identifiers

| Item | Value |
|---|---|
| **Commit SHA** | `f0e5ec6106cf7e5ee5623dc95fc44dab6d7fbb22` |
| **Commit message** | `feat(ai-scalping): deploy Volatility Gate v2 adaptive ATR floors` |
| **Railway deployment ID** | `3a9dcee0-0ecb-4aed-816a-5496750a4a87` |
| **Deployment status** | **SUCCESS** (created `2026-07-31T20:16:29.093Z`) |
| **Production SHA** | `f0e5ec6106cf7e5ee5623dc95fc44dab6d7fbb22` (Railway `meta.commitHash`) |
| **Previous production SHA** | `76344ca12b35763be02d682de4894d0dcae1e9b5` (deployment `f9113624-…`, now REMOVED) |
| **Branch** | `main` → `origin/main` |
| **Service URL** | `https://quantforg-production.up.railway.app` |
| **Config version** | `ai-scalping-v7.2.0` |

---

## What was deployed (scope)

| Path | Role |
|---|---|
| `app/domain/institutional_trading/ai_scalping/volatility_gate_v2.py` | Adaptive ATR model |
| `app/domain/institutional_trading/ai_scalping/quality_gates.py` | Wire v2 + evidence |
| `app/domain/institutional_trading/ai_scalping/scoring.py` | Pass MTF/regime; record decision |
| `app/domain/institutional_trading/ai_scalping/config.py` | Floors + exceptional knobs |
| `app/domain/institutional_trading/ai_scalping/__init__.py` | Exports |
| `tests/unit/test_volatility_gate_v2.py` | Unit + before/after replay |
| `docs/trading/VOLATILITY_GATE_V2_REPORT.md` | Design / acceptance |
| `docs/trading/VOLATILITY_GATE_CALIBRATION_REPORT.md` | Calibration evidence |

**Not deployed in this commit:** Risk Engine, PRE, Dynamic Position Sizing, OMS, MT5, unrelated investigation artifacts.

---

## Proof Production is no longer on Volatility Gate v1

1. **Railway deployment meta** binds active SUCCESS deploy `3a9dcee0-…` to commit **`f0e5ec6…`**, whose message and tree introduce `volatility_gate_v2.py` and replace the single fixed `atr_low_pct/2` check in `quality_gates.py`.  
2. **Previous live SHA `76344ca`** (AI pipeline sync only) did **not** contain Volatility Gate v2; that deployment is **REMOVED**.  
3. **Config identity on that SHA:** `DEFAULT_AI_SCALPING_CONFIG.version = ai-scalping-v7.2.0` with `volatility_gate_v2` block in `to_dict()` — v1 had no adaptive exceptional/hard floors.  
4. **Live reject path** still surfaces as `AI quality gates rejected — NO_TRADE` (executable-direction collapse), but the underlying gate module on this SHA is **`evaluate_volatility_gate_v2`** (`model=volatility_gate_v2`), not the former inline `atr_pct < atr_low_pct/2` only.

---

## Confirmed floors (production commit)

| Floor | Value | Status |
|---|---|---|
| Standard compression floor | **0.20%** | Confirmed (`atr_compression_floor_pct`) |
| Exceptional adaptive path | **0.15%** | Confirmed (`atr_exceptional_floor_pct`) |
| Hard minimum | **0.15%** | Confirmed (`atr_hard_min_pct`) |
| Quality floor | ≥ **80** (normal adaptive **82**, low-vol adaptive **88**) | Preserved |
| Confidence floor | ≥ **80** (normal **82**, low-vol **88**) | Preserved |

Exceptional path still requires all institutional strength pillars (Q/C/MTF/liquidity/spread/session/regime/…).

---

## Live verification (post-deploy)

| Check | Result |
|---|---|
| `/health` | **200** `{"status":"ok"}` |
| Railway service | **Online** on deploy `3a9dcee0-…` |
| Auto-trading cycles | **Running** (continuous `NO_TRADE` cycles observed) |
| Sample post-deploy cycle | `2026-07-31T20:20:15Z` · XAUUSD · session `new_york` |
| Quality | **89** (≥ 80) |
| Confidence | **92** (≥ 80) |
| MTF | **PASS** (score 100, H1+M15 lock) |
| Liquidity v2 | **PASS** (OB/FVG sources present) |
| ATR% (live) | **≈ 0.13%** |
| Volatility Gate v2 | **FAIL expected** — hard minimum (`0.13 < 0.15`) |
| Reproduced decision | `Volatility below hard minimum ATR%=0.13 < 0.15 (evidence dead-tape floor)` · `model=volatility_gate_v2` |
| OMS | **Not called** (`forwarded_to_oms=False`) |
| Open positions | **0** |
| Equity | **181.53** |

No forced trades. Strategy unchanged aside from the approved volatility gate.

---

## Deployment sequence executed

1. Verified working tree; staged **only** Vol Gate v2 implementation + tests + design/calibration docs.  
2. Committed on `main`: `f0e5ec6`.  
3. Pushed to `origin/main` (`76344ca..f0e5ec6`).  
4. Railway auto-deployed; deploy **`3a9dcee0-…` → SUCCESS**.  
5. Verified Production SHA = `f0e5ec6` via deployment `meta.commitHash`.  
6. Confirmed floors 0.20 / 0.15 / 0.15.  
7. Re-ran live observation (health, cycles, gateway).

---

## Conclusion

**Production is running Volatility Gate v2** on commit **`f0e5ec6`** / deploy **`3a9dcee0-0ecb-4aed-816a-5496750a4a87`**.  
Standard **0.20%**, exceptional **0.15%**, hard min **0.15%**. Quality/Confidence floors preserved. Live market ATR% ≈ 0.13 correctly remains below hard minimum (no OMS fill) — expected institutional behavior, not a deploy failure.
