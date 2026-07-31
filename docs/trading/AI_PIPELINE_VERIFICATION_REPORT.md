# AI Pipeline Verification Report

**Investigation type:** Observe-only — no threshold, quality, confidence, safety, or strategy changes  
**Generated at:** 2026-07-31T19:20:00Z  
**Related:** [`LIVE_TRADING_ROOT_CAUSE_REPORT.md`](./LIVE_TRADING_ROOT_CAUSE_REPORT.md)

---

## Executive answer

Production is **not** running M15 Trend Semantics v2, Liquidity v2, or Score Pipeline Integration.

It is running the **legacy ITE stack** (`config_version=ite-v1.0.0`) on Railway commit:

`30fb60f50d1483a1c0fa6ab9719b984e28831097`

The approved AI improvements exist only on **unmerged feature branches**. Live MTF score **45** with `H4=range H1=down M15=range M5=up` is an exact match to the **legacy** `TrendEngine` weight math — not MTF v2.

---

## Production SHA vs approved AI SHAs

| Artifact | SHA / version | On production? | On `origin/main`? |
|---|---|---|---|
| Railway production deploy | `30fb60f…` | **YES (running)** | YES |
| Legacy ITE config | `ite-v1.0.0` | **YES** | YES |
| AI Decision Engine v2 | `a5c4971` → `ite-v2.0.0` | **NO** | **NO** |
| MTF alignment diagnostic | `2a780ca` | **NO** | **NO** |
| M15 Trend Semantics v2 | `41e1fce` → `ite-v2.1.0` | **NO** | **NO** |
| Score Pipeline Integration | `035903e` → `ite-v2.2.0` | **NO** | **NO** |

`git merge-base --is-ancestor` for `a5c4971`, `41e1fce`, and `035903e` against both production SHA and `origin/main` → **not ancestors**.

---

## Task results

### 1. Which MTF engine is loaded in production?

**Legacy `TrendEngine`** in `app/domain/institutional_trading/trend_engine.py` (ite-v1.0.0).

| Check | Production | Approved (branch) |
|---|---|---|
| Module | `trend_engine.py` only | + `mtf_v2.py` regime policies |
| File `mtf_v2.py` on prod tree | **MISSING** | Present on `035903e` |
| Live reason format | `MTF down: H4=range H1=down M15=range M5=up score=45 not aligned` | MTF v2 would cite regime/policy (`v2_ranging` / H1+M15 lock) |
| Score reproduction | Legacy weights → **exactly 45** (see below) | Ranging policy: H4 weight **0** (context only) |

**Legacy score math for the live frame set:**

| Role | TF state | Weight | Contribution |
|---|---|---|---|
| macro (H4) | range | 40 | 10 (`w//4`) |
| primary (H1) | down (=bias) | 30 | 30 |
| entry (M15) | range | 20 | 5 (`w//4`) |
| execution (M5) | up (opposite) | 10 | 0 |
| **Total** | | | **45** |

Bias falls back from H4 RANGE → H1 DOWN. Alignment requires score ≥ 55 (scalping) or H4==H1 lock (swing) → **not aligned**. Structure/BOS/CHOCH/OB/FVG **do not enter** this MTF score — only TF direction labels do. That is why MTF can stay at 45 while SMC artefacts exist.

---

### 2. Is M15 Trend Semantics v2 active?

**NO.**

| Evidence | Result |
|---|---|
| `app/domain/institutional_trading/m15_semantics_v2.py` on prod | **MISSING** |
| `m15_semantics_telemetry.py` on prod | **MISSING** |
| Commit `41e1fce` in prod/`main` | **NOT present** |
| Branch | `origin/cursor/m15-trend-semantics-v2-bc83` (ahead of main; **not merged**) |
| Deployment audit | PR **#52 OPEN**; Vercel preview **SKIPPED** (branch work not on approved Production tip) |
| Live behavior | M15 raw `range` scored as weak partial; no `PULLBACK_WITHIN_TREND` / `CONSOLIDATION` rewrite |

Approved v2 intent (not in prod): when H1 stays directional, M15 RANGE/DOWN can be classified as pullback/consolidation instead of hard opposition; M5 never redefines direction.

---

### 3. Is Liquidity v2 active?

**NO.**

| Evidence | Result |
|---|---|
| `app/domain/institutional_trading/liquidity_v2.py` on prod | **MISSING** |
| Commit `a5c4971` / `035903e` in prod/`main` | **NOT present** |
| Production confluence liquidity gate | Legacy: only `sweeps` / `pools` / `equal_highs` / `equal_lows` |
| Live rejection code | `no_liquidity_context` **while** cycle reasons also report `Active order blocks=1` and `Open FVGs=4` |

That contradiction is the smoking gun for **legacy** liquidity context:

```141:148:app/domain/institutional_trading/confluence.py
        liq = snapshot.liquidity
        if liq and (liq.sweeps or liq.pools or liq.equal_highs or liq.equal_lows):
            sweep_n = len(liq.sweeps)
            factors["liquidity"] = 85 if sweep_n else 65
            reasons.append(f"Liquidity present sweeps={sweep_n} pools={len(liq.pools)}")
        else:
            factors["liquidity"] = 20
            rejected.append("no_liquidity_context")
```

Approved Liquidity v2 (not in prod) treats validated/active OB, respected FVG, displacement-qualified OB, sweeps, EQH/EQL, pools, etc. as valid context — **without lowering 80/80 floors**.

---

### 4. Is Score Pipeline Integration active?

**NO.**

| Evidence | Result |
|---|---|
| Commit `035903e` (`ite-v2.2.0`) in prod/`main` | **NOT present** |
| `score_pipeline_integration_replay.py` on prod | **MISSING** |
| `tests/unit/test_score_pipeline_integration.py` on prod | **MISSING** |
| Branch | `origin/cursor/score-pipeline-integration-bc83` (**not merged**) |
| PR / preview | PR **#54 OPEN**; Vercel promotion **SKIPPED** |

Approved integration (not in prod):

- Wire Liquidity v2 into Quality
- Credit M15 after H1+M15 lock (semantics-aware)
- Deduplicate Confidence penalties already scored in Quality
- **Thresholds remain 80/80; weights unchanged**

---

### 5. Does Quality still use legacy liquidity scoring?

**YES.**

Production `TradeQualityEvaluator._liquidity()` still uses the **sweep/pool/EQH/EQL-only** path:

```97:120:app/domain/institutional_trading/trade_quality.py
    def _liquidity(self, snap: LiquiditySnapshot | None) -> TradeQualityFactor:
        ...
        sweeps = len(getattr(snap, "sweeps", ()) or ())
        pools = len(getattr(snap, "pools", ()) or ())
        eqh = len(getattr(snap, "equal_highs", ()) or ())
        eql = len(getattr(snap, "equal_lows", ()) or ())
        score = 40
        if sweeps:
            score += 30
        ...
```

Approved `035903e` replaces this with `_liquidity_v2(...)` calling `evaluate_liquidity_v2` (OB/FVG-aware). **Not deployed.**

---

### 6. Does Confidence still use duplicated penalties?

**YES (legacy confluence path).**

Production confluence independently scores structure / OB / FVG / liquidity / quality again after Quality already graded related facts. Score Pipeline Integration adds `_dedup_passthrough` so Confidence **reuses** Quality factor scores when already at bar — **eliminating double penalties without raising ceilings**. That helper and call sites exist only on `035903e`, not on production.

---

### 7. Does production AI decision pipeline match the latest approved implementation?

**NO.**

| Layer | Production (running) | Latest approved branch tip |
|---|---|---|
| Config version | `ite-v1.0.0` | `ite-v2.2.0` |
| MTF | Legacy directional weights; H4 RANGE still costs score | MTF v2 regime: H4 RANGE = context, not veto |
| M15 | Raw TF direction | Semantics v2 pullback taxonomy |
| Liquidity (Quality) | Sweep-centric legacy | Liquidity v2 |
| Liquidity (Confidence) | Sweeps/pools/EQ only → `no_liquidity_context` despite OB/FVG | Liquidity v2 context |
| Confidence vs Quality | Independent re-penalties | Deduped score pipeline |
| Floors | 80 / 80 | 80 / 80 (**unchanged in approved work**) |

---

## Why production missed the approved AI work

1. **Never merged to `main`.** Merge-audit (`docs/deployment/FULL_DEPLOYMENT_AUDIT.md`) lists:
   - `cursor/m15-trend-semantics-v2-bc83` → **NO** (not on main)
   - `cursor/score-pipeline-integration-bc83` → **NO**
   - `cursor/mtf-alignment-diagnostic-bc83` → **NO**
2. **PRs still OPEN** (#52, #54 per audit) — not squash-merged into the production tip.
3. **Vercel Production promotion correctly SKIPPED** those preview SHAs because they were **not on the approved Production git tip** (rule: do not overwrite newer Production with older unmerged branch tips). That skip was a promotion-safety decision; it does **not** mean the AI work is live.
4. Production tip advanced with docs/UI/pricing/auth merges (`30fb60f`, etc.) **without** bringing AI Decision Engine v2 → M15 v2 → Score Pipeline commits along.

---

## Missing approved improvements (exact list)

| # | Approved improvement | Commit | Target version | Status on production |
|---|---|---|---|---|
| 1 | AI Decision Engine v2 — regime MTF + liquidity context | `a5c4971` | `ite-v2.0.0` | **Missing** |
| 2 | MTF alignment diagnostic (evidence-only) | `2a780ca` | (diagnostic) | **Missing** |
| 3 | M15 Trend Semantics v2 — pullback taxonomy + H1+M15 lock | `41e1fce` | `ite-v2.1.0` | **Missing** |
| 4 | Score Pipeline Integration — Liquidity v2 + M15/MTF into Q/C + confidence dedup | `035903e` | `ite-v2.2.0` | **Missing** |

**Not missing / must not change:** Quality floor 80, Confidence floor 80, Risk Engine, OMS, MT5, safety gates.

---

## Interpretation of current live rejects

Given production is on **legacy** AI:

- MTF **45** + `mtf_not_aligned` with H4 RANGE is **expected** under v1 weights.
- `no_liquidity_context` **alongside** active OB + open FVG is **expected** under legacy liquidity rules — and is precisely what Liquidity v2 was approved to correct **without** lowering 80/80.
- Therefore we **cannot** conclude that “the market has produced no institutional-grade setup under the approved v2 pipeline.” We can only conclude the **legacy** pipeline rejected these cycles.

Whether v2 would have passed these same bars requires a **synchronized deploy + replay** (out of scope for this verify-only report). No threshold lowering is implied or recommended.

---

## Recommended next step (do not implement in this report)

1. Merge the approved chain onto `main` in order: `a5c4971` → `41e1fce` → `035903e` (plus diagnostic if desired), preserving **80/80**.
2. Deploy that SHA to Railway production.
3. Re-run live cycle evidence / offline replay to compare false-negative rate — still without lowering floors.

---

## Final conclusion

**B. Production AI pipeline is running an older implementation and requires synchronization.**
